"""Набор функций, запускаемых через WSGI-приложение ля сбора статистики с сетевых сегментов дата-центров
и получения данных о хостах в сетевых сегментах дата-центров."""

__author__ = "ZHEZLYAEV Aleksandr  <zhezlyaev@gmail.com>"
__version__ = "1.0"

# -*- coding: utf-8 -*-

import io
import ipaddress
import json
import os
import pathlib
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from itertools import repeat
from typing import Final, Literal

from flask import current_app
from flask_socketio import emit
from mac_vendor_lookup import InvalidMacError, MacLookup, VendorNotFoundError
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from tabulate import tabulate

from DCSegment import DCSegment
from utils.net.BaseNetTools import BaseNetTools
from utils.net.SSHconnect import SSHconnect
from utils.net.zLog import zLog

# подключение к БД через SQLAlchemy
sqlite_database = "sqlite:///net.db"

# создаем движок SQLAlchemy
engine = create_engine(sqlite_database)

# создаем класс сессии
Session = sessionmaker(autoflush=False, bind=engine)


# создаем базовый класс для моделей БД SQLAlchemy
class Base(DeclarativeBase):
    """Базовый класс для моделей."""


# создаем модель, объекты которой будут храниться в бд
class NetDevice(Base):
    """Класс для представления таблицы NetDevice в БД для SQLAlchemy."""

    __tablename__ = "netdevices"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    dc = Column(String(10), nullable=False)
    hostname = Column(String(50), unique=True, nullable=False)
    netos = Column(String(50), nullable=False)
    role = Column(String(50), nullable=False)

    def __repr__(self):
        return f"{self.hostname} [{self.netos}]"


# для корректной работы emit внутри функции, которая запускается через ThreadPoolExecutor
app = current_app._get_current_object()


def socketio_logger(func):
    """Декоратор для отправки логов из stdout в wsgi через SocketIO."""

    def wrapper(*args, **kwargs):
        # делаем до выполнения декорируемой функции
        log_capture_string = io.StringIO()
        buff_logger = zLog(buffer_capture=log_capture_string)

        # декарируемая функция
        result = func(*args, buff_logger=buff_logger, **kwargs)

        # делаем после выполнения декорируемой функции
        log_msg_from_buffer = log_capture_string.getvalue()
        emit("server_info_messages", {"data": f"{log_msg_from_buffer}"}, broadcast=True, namespace="/")
        log_capture_string.truncate(0)

        return result

    return wrapper


@socketio_logger
def send_log_via_soketio(
    message: str, level: Literal["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"], buff_logger
):
    """Функция отправляет логи через Socket IO в JavaScript и пишет логи в лог-
    файл."""

    if level == "DEBUG":
        buff_logger.log(log_to="bufferAndFile").debug(message)

    elif level == "INFO":
        buff_logger.log(log_to="bufferAndFile").info(message)

    elif level == "SUCCESS":
        buff_logger.log(log_to="bufferAndFile").success(message)

    elif level == "WARNING":
        buff_logger.log(log_to="bufferAndFile").warning(message)

    elif level == "ERROR":
        buff_logger.log(log_to="bufferAndFile").error(message)

    elif level == "CRITICAL":
        buff_logger.log(log_to="bufferAndFile").critical(message)


def check_vlan_info_date():
    """Функция проверяет дату создания файла VLANS.json и отдает сообщение с
    данными через Socket IO."""

    VLAN_DATA_DIR: Final = "Data"
    vlan_count = 0

    files = os.listdir(VLAN_DATA_DIR)
    num_of_files = len(files)
    n = 0

    for file in files:
        n = n + 1
        with open(VLAN_DATA_DIR + "/" + file) as f:
            all_vlans_by_dc: dict = json.load(f)
            vlan_count = vlan_count + len(all_vlans_by_dc.keys())
            # узнаем дату создания последнего файла
            if n == num_of_files:
                vlans_data_date = datetime.fromtimestamp(os.path.getmtime(VLAN_DATA_DIR + "/" + file))

    current_datetime = datetime.now()

    if (current_datetime - vlans_data_date) > timedelta(days=1):
        vlan_ver_msg = f"Версия БД VLAN ID получена более 1 дня назад. Последнее обновление - {vlans_data_date.strftime('%d.%m.%Y %H:%M:%S')}"
    else:
        vlan_ver_msg = f"Количество известных VLAN ID - {vlan_count}. Последнее обновление - {vlans_data_date.strftime('%d.%m.%Y %H:%M:%S')}"

    return vlan_ver_msg


def get_vlans_in_threads(username: str, password: str):
    """Функция получает информацию о SVI со всех устройств (в потоках)."""

    OTV_VLAN_DATA: Final = "Data/otv_vlans.json"
    MSK34_VLAN_DATA: Final = "Data/msk34_vlans.json"
    MSK70_VLAN_DATA: Final = "Data/msk70_vlans.json"
    MSKD8_VLAN_DATA: Final = "Data/mskd8_vlans.json"

    msk34_dci_vlans = set()
    msk70_dci_vlans = set()
    mskd8_dci_vlans = set()

    msk34_only_vlans = set()
    msk70_only_vlans = set()
    mskd8_only_vlans = set()

    netdev_connection_params: list[dict[str, str]] = []

    # получаем данные о сетевых устройствах (VDC с SVI) из БД
    with Session(autoflush=False, bind=engine) as db:
        netdevs_db_query_result = db.query(NetDevice).filter_by(role="dc_core_gateway").all()
        for result in netdevs_db_query_result:
            netdev_connection_params.append(dict([("netdev_name", result.hostname), ("os", result.netos)]))

    with ThreadPoolExecutor(max_workers=6) as executor:
        generator = executor.map(get_vlans_single_netdev, netdev_connection_params, repeat(username), repeat(password))

        # с помощью zip "склеиваем" данные dc_core_netdev_host <-> результат выполнения функции, чтобы потом можно было понимать какие данные взяты с какого DC CORE
        for device_dict, generator_output in zip(netdev_connection_params, generator):
            dc_core_netdev_host = device_dict.get("netdev_name")
            for vlan_dict in generator_output:
                vlan_id = int(vlan_dict.get("vlan_id"))

                # перебираем не растянутые vlan
                if 1 < vlan_id < 1000:
                    if "MSK34" in dc_core_netdev_host:
                        msk34_only_vlans.add(vlan_id)

                    elif "MSK70" in dc_core_netdev_host:
                        msk70_only_vlans.add(vlan_id)

                    elif "MSKD8" in dc_core_netdev_host:
                        mskd8_only_vlans.add(vlan_id)

                # перебираем растянутые vlan
                elif 999 < vlan_id < 4097:
                    if "MSK34" in dc_core_netdev_host:
                        msk34_dci_vlans.add(vlan_id)
                    elif "MSK70" in dc_core_netdev_host:
                        msk70_dci_vlans.add(vlan_id)
                    elif "MSKD8" in dc_core_netdev_host:
                        mskd8_dci_vlans.add(vlan_id)

    # находим общие 4-х значные DCI VLANS для всех DC CORE устройств площадок MSK34 MSK70 MSKD8
    dci_vlans = msk34_dci_vlans.union(msk70_dci_vlans).union(mskd8_dci_vlans)
    dci_vlans = sorted(dci_vlans)

    # словарь соответствия vlan <-> DC
    otv_vlans_for_check: dict = {}

    msk34_vlans_for_check: dict = {}
    msk70_vlans_for_check: dict = {}
    mskd8_vlans_for_check: dict = {}

    # определяем на каких устройствах есть otv svi
    for vlan in dci_vlans:
        current_netdevs_list = []
        if vlan in msk34_dci_vlans:
            for net_dict in netdev_connection_params:
                if "MSK34" in net_dict.get("netdev_name"):
                    current_netdevs_list.append(net_dict)

        if vlan in msk70_dci_vlans:
            for net_dict in netdev_connection_params:
                if "MSK70" in net_dict.get("netdev_name"):
                    current_netdevs_list.append(net_dict)

        if vlan in mskd8_dci_vlans:
            for net_dict in netdev_connection_params:
                if "MSKD8" in net_dict.get("netdev_name"):
                    current_netdevs_list.append(net_dict)

        otv_vlans_for_check[vlan] = current_netdevs_list

    # определяем на каких устройствах есть msk34 svi
    for vlan in msk34_only_vlans:
        current_netdevs_list = []
        for net_dict in netdev_connection_params:
            if "MSK34" in net_dict.get("netdev_name"):
                current_netdevs_list.append(net_dict)

        msk34_vlans_for_check[vlan] = current_netdevs_list

    # определяем на каких устройствах есть msk70 svi
    for vlan in msk70_only_vlans:
        current_netdevs_list = []
        for net_dict in netdev_connection_params:
            if "MSK70" in net_dict.get("netdev_name"):
                current_netdevs_list.append(net_dict)

        msk70_vlans_for_check[vlan] = current_netdevs_list

    # # определяем на каких устройствах есть mskd8 svi
    for vlan in mskd8_only_vlans:
        current_netdevs_list = []
        for net_dict in netdev_connection_params:
            if "MSKD8" in net_dict.get("netdev_name"):
                current_netdevs_list.append(net_dict)

        mskd8_vlans_for_check[vlan] = current_netdevs_list

    pathlib.Path("Data").mkdir(parents=True, exist_ok=True)

    # Записываем данные о otv vlan в json
    with open(OTV_VLAN_DATA, "w") as f:
        json.dump(otv_vlans_for_check, f, sort_keys=True, indent=3)

    # Записываем данные о otv vlan в json
    with open(MSK34_VLAN_DATA, "w") as f:
        json.dump(msk34_vlans_for_check, f, sort_keys=True, indent=3)

    # Записываем данные о otv vlan в json
    with open(MSK70_VLAN_DATA, "w") as f:
        json.dump(msk70_vlans_for_check, f, sort_keys=True, indent=3)

    # Записываем данные о otv vlan в json
    with open(MSKD8_VLAN_DATA, "w") as f:
        json.dump(mskd8_vlans_for_check, f, sort_keys=True, indent=3)

    # Проверяем время создания "Data/VLANS.json" и отдаем эти данные через Soket IO в JavaScript
    vlan_info_msg = check_vlan_info_date()
    emit("update_vlan_info_reply", vlan_info_msg, broadcast=True, namespace="/")


def get_vlans_single_netdev(dc_core_dict, username, password):
    """Вспомогательная функция для функции get_vlans_in_threads.

    Эта функция, запускаемая в потоках.
    """

    with app.app_context():
        netdev_host = dc_core_dict.get("netdev_name")
        netdev_os = dc_core_dict.get("os")

        # собираем информацию о vlan с устройств DC CORE
        with SSHconnect(netdev_host, username, password, netdev_os) as ssh_conn:
            # создаем экземпляр класса BaseNetTools и получаем информацию о VLAN
            current_netdev = BaseNetTools(ssh_conn)
            vlans_info = current_netdev.get_all_vlan_info()

            return vlans_info


def get_hosts_in_threads(username: str, password: str, vlan, dc):
    """Функция получает информацию о хостах сетевого сегмента (в потоках)."""

    OTV_VLAN_DATA: Final = "Data/otv_vlans.json"
    MSK34_VLAN_DATA: Final = "Data/msk34_vlans.json"
    MSK70_VLAN_DATA: Final = "Data/msk70_vlans.json"
    MSKD8_VLAN_DATA: Final = "Data/mskd8_vlans.json"
    REPORTS_DIR: Final = "Reports"

    # cловарь хранит уже установленные SSH сессии, чтобы не ставить их заново при необходимости
    ssh_connections_dict = {}

    # финальный словарь с сетеввыми сегменатами DC для записи в JSON
    to_json_all: dict = {}

    # словарь, по которому проверяем клиентов в соответствии с vlan id
    vlans_for_check: dict = {}

    if dc == "ALL":
        with open(OTV_VLAN_DATA) as f:
            all_vlan_json: dict = json.load(f)
    elif dc == "MSK34":
        with open(MSK34_VLAN_DATA) as f:
            all_vlan_json: dict = json.load(f)
    elif dc == "MSK70":
        with open(MSK70_VLAN_DATA) as f:
            all_vlan_json: dict = json.load(f)
    elif dc == "MSKD8":
        with open(MSKD8_VLAN_DATA) as f:
            all_vlan_json: dict = json.load(f)

    if vlan == "ALL":
        vlans_for_check.update(all_vlan_json)
    else:
        if vlan in all_vlan_json:
            vlans_for_check[str(vlan)] = all_vlan_json.get(str(vlan))
        else:
            if len(vlan) < 4:
                send_log_via_soketio(f"SVI {vlan} не является растянутым vlan", level="ERROR")
            else:
                send_log_via_soketio(
                    f"SVI {vlan} является растянутым, но для поиска выбран локальный ЦОД {dc}", level="ERROR"
                )
            emit("closeConnection", broadcast=True, namespace="/")
            return False

    number_of_vlans = len(vlans_for_check)

    def get_hosts_info_in_threads(dc_core_dict) -> dict:
        """Вспомогательная функция для функции get_hosts_in_threads.

        Эта функция, запускаемая в потоках.
        """

        with app.app_context():
            # множество, куда попадает arp-записи с одного сетевого шлюза
            current_netdev_segment_arp_data: list = []

            dc_core_netdev_host = dc_core_dict.get("netdev_name")
            dc_core_netdev_os = dc_core_dict.get("os")

            # Если SSH соединение уже установлено - перепрыгиваем на него.
            if ssh_connections_dict.get(dc_core_netdev_host):
                ssh_conn = ssh_connections_dict.get(dc_core_netdev_host)

            else:
                ssh = SSHconnect(dc_core_netdev_host, username, password, device_type=dc_core_netdev_os)
                ssh_conn = ssh.connect()
                send_log_via_soketio(
                    f"{dc_core_netdev_host} [{dc_core_netdev_os}] - SSH соединение установлено", level="INFO"
                )

                # добавляем информацию о установленной SSH-сессии в словарь, если её ранее там не было, чтобы в дальнейшем не ставить новое SSH соединение
                ssh_connections_dict[dc_core_netdev_host] = ssh_conn

            # добавляем в список сетевые шлюзы, где есть текущий интерфейс
            vlan_dc.append(dc_core_netdev_host)

            # новый экземпляр класса BaseNetTools для текущей SSH-сессии
            current_dc_core_netdev = BaseNetTools(ssh_conn)

            # Заходим на оборудование и убеждаемся, что SVI в UP + получаем и парсим arp-таблицу
            intf_output = current_dc_core_netdev.get_interface(vlan_id)
            intf_link_status = intf_output[0].get("link_status")
            intf_description = intf_output[0].get("description")

            # если интерфейс не в UP, пропускаем дальнейшие действия и переходим к другому устройству
            if intf_link_status != "up":
                send_log_via_soketio("{ssh_conn.host} - Interface SVI {vlan_id} is in DOWN state", level="ERROR")
                return False

            # получаем данные с IP интерфейса
            ip_intf_output = current_dc_core_netdev.get_ip_interface(vlan_id)

            intf_name = ip_intf_output[0].get("interface")
            vrf_name = ip_intf_output[0].get("vrf_name")
            primary_ip_subnet = ip_intf_output[0].get("primary_ip_subnet")
            secondary_ip_subnet = ip_intf_output[0].get("secondary_ip_subnet")

            # список с IP-сетями, которые настроены на интерфейсе
            ip_subnets = []
            ip_subnets.append(primary_ip_subnet)
            if secondary_ip_subnet:
                ip_subnets.extend(secondary_ip_subnet)

            # получаем arp таблицу по нашим сетям, настроенных на интерфейсе
            arp_output = current_dc_core_netdev.get_ip_arp(intf=intf_name, vrf=vrf_name)
            for arp_value_dict in arp_output:
                ip_address = arp_value_dict.get("ip_address")
                mac_address = arp_value_dict.get("mac_address")

                if mac_address == "INCOMPLETE":
                    continue

                arp_value: tuple = (ip_address, mac_address)
                current_netdev_segment_arp_data.append(arp_value)

            current_netdev_segment_info = {
                "vrf_name": vrf_name,
                "intf_description": intf_description,
                "ip_subnets": ip_subnets,
                "arp_data": current_netdev_segment_arp_data,
            }

            return current_netdev_segment_info

    current_vlan_number = 0
    for vlan_id, dci_vlan_netdevs_list in vlans_for_check.items():
        current_vlan_number = current_vlan_number + 1

        # список кортежей по хостам с обработанныйми arp данными за весь сетевой сегмент
        allHostsSegmentData = []

        # список сетевых шлюзов для каждого IP интерфейса
        vlan_dc = []

        # счетчик служебных адресов ( адреса интерфейсов, адреса FHRP-протоколов )
        network_service_address_count = 0

        # множество, где хранятся уникальные arp данные за 1 интерфейс со всех устройств
        list_of_tupples_segment_arp_data: list = []

        send_log_via_soketio(f"Начинаю сбор информации о хостах интерфейса SVI {vlan_id}", level="INFO")

        # в параллельных потоках подключаемся к шлюзам DC (вызываем фунцию GetVlanInThreads одновременно для разных устройств из списка MSKALLDC_SVI)
        with ThreadPoolExecutor(max_workers=6) as executor:
            generator = executor.map(get_hosts_info_in_threads, dci_vlan_netdevs_list)
            for generator_output, device_dict in zip(generator, dci_vlan_netdevs_list):
                if generator_output:
                    list_of_tupples_segment_arp_data.append(generator_output.get("arp_data"))
                else:
                    send_log_via_soketio(
                        f"{device_dict.get('netdev_name')} ERROR to collect data about hosts on SVI {vlan_id}",
                        level="ERROR",
                    )

        # список списков преобразуем в 1 список
        segment_arp_data: list = sum(list_of_tupples_segment_arp_data, [])

        # список преобразуем в множество и обратно для избавления от дублей
        segment_arp_data: set = list(set(segment_arp_data))

        # сортируем список по 1 элементу во вложенном списке и сортировка этого элемента выполняется по увеличению IP-адреса
        segment_arp_data.sort(key=lambda x: ipaddress.IPv4Address(x[0]))

        # парсим arp таблицу и выделяем нужные нам данные
        for host_ip_and_mac in segment_arp_data:
            hostIPAddress = host_ip_and_mac[0]
            hostMacAddress = host_ip_and_mac[1]

            # определяем DNS HOSTNAME
            try:
                hostDnsName = socket.gethostbyaddr(hostIPAddress)[0]
            except socket.herror:
                hostDnsName = "UnknownHostName"

            # определяем VENDOR TYPE
            try:
                hostVendor = MacLookup().lookup(hostMacAddress)

            except (VendorNotFoundError, InvalidMacError):
                hostVendor = "UnknownVendor"

            # считаем количество служебных адресов в сети, такие как адреса интерфейсов и FHRP протоколов
            if hostVendor in ["ICANN, IANA Department", "Cisco Systems, Inc"]:
                network_service_address_count = network_service_address_count + 1

            # собираем кортеж из данных для ARP записи
            hostData = (hostIPAddress, hostDnsName, hostMacAddress, hostVendor)

            # добавляем собранные данные по 1 хосту к другим данным для сегмента
            allHostsSegmentData.append(hostData)

        if allHostsSegmentData:
            # экземпляр data-класса DCSegment для текущего интерфейса (SVI)
            currIntfDataClass = DCSegment(
                vlan_id=vlan_id,
                vrf_name=generator_output.get("vrf_name"),
                segment_description=generator_output.get("intf_description"),
                num_of_all_active_hosts=len(allHostsSegmentData),
                num_of_network_service_hosts=network_service_address_count,
                networks=generator_output.get("ip_subnets"),
                vlan_dc=vlan_dc,
                hosts_in_segment=allHostsSegmentData,
            )

            TXTreportFilePath = REPORTS_DIR + "/" + f"report_{datetime.now().strftime('%d.%m.%Y')}.txt"
            JSONreportFilePath = REPORTS_DIR + "/" + f"report_{datetime.now().strftime('%d.%m.%Y')}.json"

            segment_statistics = (
                ("vlan id", currIntfDataClass.vlan_id),
                ("vrf name", currIntfDataClass.vrf_name),
                ("description", currIntfDataClass.segment_description),
                ("networks", ", ".join(currIntfDataClass.networks)),
                ("SVI exist on", ", ".join(currIntfDataClass.vlan_dc)),
                ("number of active hosts", currIntfDataClass.num_of_active_hosts),
                ("number of SVI & VRRP IPv4 address", currIntfDataClass.num_of_network_service_hosts),
                ("network usage in %", f"{currIntfDataClass.net_usage_in_percentage}%"),
            )

            # отправляем сообщение в Java Script через socketIO
            emit(
                "server_host_info_reply",
                {"statistics": segment_statistics, "hosts_data": currIntfDataClass.hosts_in_segment},
                broadcast=True,
                namespace="/",
            )

            headers = ["IPv4 address", "HostName", "MAC address", "Vendor"]
            pathlib.Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

            segment_report_msg = (
                f"SVI {vlan_id} REPORT (created {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}):"
                + "\n" * 2
                + tabulate(segment_statistics, tablefmt="youtrack", stralign="left")
                + "\n" * 2
                + tabulate(currIntfDataClass.hosts_in_segment, headers=headers, tablefmt="pretty", stralign="left")
                + "\n" * 3
            )
            with open(TXTreportFilePath, "a", encoding="utf-8") as dst_file:
                dst_file.write(segment_report_msg)

            # вывод файлов в json
            intf_dict: dict = {
                "VLAN_ID": currIntfDataClass.vlan_id,
                "VRF_NAME": currIntfDataClass.vrf_name,
                "DESCRIPTION": currIntfDataClass.segment_description,
                "NETWORKS": currIntfDataClass.networks,
                "SVI_EXISTS_ON": currIntfDataClass.vlan_dc,
                "NUMBER_OF_ACTIVE_HOSTS": currIntfDataClass.num_of_active_hosts,
                "NUMBER_OF_SVI_VRRP_IP_ADDRESS": currIntfDataClass.num_of_network_service_hosts,
                "NETWORK_USAGE_IN_PERCENTAGE": currIntfDataClass.net_usage_in_percentage,
                "HOSTS_IN_SEGMENT": currIntfDataClass.hosts_in_segment,
            }

            to_json: dict = {vlan_id: intf_dict}
            to_json_all.update(to_json)  # расширяем общий словарь текущим
            send_log_via_soketio(f"Сбор информации о хостах интерфейса SVI {vlan_id} завершен", level="SUCCESS")

            # сообщение для увеличения прогресс бара внутри JavaScript
            emit(
                "progressBarUpdate",
                {"current": current_vlan_number, "total": number_of_vlans},
                broadcast=True,
                namespace="/",
            )

    with open(JSONreportFilePath, "w") as json_file:
        json.dump(to_json_all, json_file, indent=3)

    # закрываем созданные ранее SSH-соединения
    for ssh_conn in ssh_connections_dict.values():
        if ssh_conn.check_config_mode():
            ssh_conn.exit_config_mode()

        if ssh_conn.is_alive():
            ssh_conn.disconnect()
            send_log_via_soketio(f"SSH соединение с {ssh_conn.host} [{ssh_conn.device_type}] закрыто", level="INFO")

    emit("closeConnection", broadcast=True, namespace="/")
