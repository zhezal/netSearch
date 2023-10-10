"""Useful classes for ssh connecting to network infrastructure.

Usage example:

netdevs = ["192.168.1.1", "192.168.1.2", "192.168.100.3"]
for netdev in netdevs:
    ssh = SSHConnect(netdev, "user", "password", log_to="all")
    ssh_conn = ssh.connect()
    out = ssh_conn.send_command("sh clock")
    print(out)
    ssh.disconnect()


Usage example with context manager:

netdevs = ["192.168.1.1", "192.168.1.2", "192.168.100.3"]
for netdev in netdevs:
    with SSHConnect(netdev, "user", "password", log_to="all") as ssh:
        out = ssh.send_command("sh clock")
        print(out)
"""

__author__ = "ZHEZLYAEV Aleksandr <zhezlyaev@gmail.com>"
__version__ = "1.0"

# -*- coding: utf-8 -*-

import datetime
import ipaddress
import pathlib
import socket
from string import ascii_letters, digits, punctuation
from typing import Literal, Optional

from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoAuthenticationException, NetMikoTimeoutException
from netmiko.ssh_autodetect import SSHDetect


class CheckCredentials:
    """Data descriptor for checking credentials."""

    def __set_name__(self, owner, name):
        self.name = "__" + name

    def __get__(self, instance, owner):
        return getattr(instance, self.name)

    def __set__(self, instance, value):
        self._verify_credentials(value)
        setattr(instance, self.name, value)

    @staticmethod
    def _verify_credentials(crd: str) -> None:
        """The method checks the correct format of the credentials entered
        data."""
        if not isinstance(crd, str):
            raise TypeError("Login and password value must be a string.")

        letters = ascii_letters + digits + punctuation
        for s in crd:
            if len(s) < 1:
                raise TypeError("At least one character must be entered")
            if len(s.strip(letters)) != 0:
                raise TypeError("The user's credentials must contain ascii letters, digits or punctuation only.")


class SSHconnect:
    """The class determines the type of OS of the network device and
    establishes a ssh session on it."""

    __slots__ = (
        "__username",
        "__password",
        "_netdev_host",
        "_secret",
        "session_log",
        "port",
        "_device_type",
        "ssh_conn",
        "logger",
    )

    username = CheckCredentials()
    password = CheckCredentials()

    def __init__(
        self,
        netdev_host: str,
        username: str,
        password: str,
        secret: Optional[str] = None,
        device_type: Optional[str] = None,
        port: Optional[int] = 22,
    ) -> None:
        """SSHConnect class __init__."""

        self.netdev_host = netdev_host
        self.__username = username
        self.__password = password
        self._secret = secret
        self.device_type = device_type
        self.port = port
        self.session_log = f"log/netdev_log/{self.netdev_host}/{self.netdev_host}_{self.__username}_{datetime.datetime.now().strftime('%d.%m.%Y_%H.%M.%S')}.log"

        # create folder for logs
        pathlib.Path(f"log/netdev_log/{self.netdev_host}").mkdir(parents=True, exist_ok=True)

    @property
    def netdev_host(self):
        """Getter for network device hostname."""
        return self._netdev_host

    @netdev_host.setter
    def netdev_host(self, netdev_host):
        """Setter for network device hostname."""
        self._verify_netdev_host(netdev_host)
        self._netdev_host = netdev_host

    @staticmethod
    def _verify_netdev_host(netdev_host: str) -> None:
        """The method checks the validity of the dns record if it is passed as
        an argument."""
        if not isinstance(netdev_host, str):
            raise TypeError("The network device hostname value must be a string.")

        netdev_host_iр = socket.gethostbyname(netdev_host)
        ipaddress.ip_interface(netdev_host_iр)

    @property
    def device_type(self):
        """Getter for network device type."""
        return self._device_type

    @device_type.setter
    def device_type(self, device_type):
        """Setter for network device type."""
        self._verify_device_type(device_type)
        self._device_type = device_type

    @staticmethod
    def _verify_device_type(device_type: str) -> None:
        """The method checks the correctness of the network device type."""
        if device_type is not None:
            if not isinstance(device_type, str):
                raise TypeError("The network device type value must be a string.")

            device_type_lst = ["cisco_ios", "cisco_nxos", "huawei"]

            if device_type not in device_type_lst:
                raise TypeError(f"{device_type} - This type of network device is not supported..")

    def __enter__(self):
        if self.device_type:
            device_type = self.device_type
        else:
            device_type = self.get_netdev_os()

        ssh_conn_params = {
            "device_type": device_type,
            "host": self.netdev_host,
            "username": self.__username,
            "password": self.__password,
            "secret": self._secret,
            "port": self.port,
            "session_log": self.session_log,
            "fast_cli": False,
        }

        self.ssh_conn = ConnectHandler(**ssh_conn_params)
        return self.ssh_conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.ssh_conn.check_config_mode():
            self.ssh_conn.exit_config_mode()

        if self.ssh_conn.is_alive():
            self.ssh_conn.disconnect()

    def get_netdev_os(self) -> str:
        """Returns a string describing the OS of the network device."""

        autodetect_ssh_conn_params = {
            "device_type": "autodetect",
            "host": self.netdev_host,
            "username": self.__username,
            "password": self.__password,
            "secret": self._secret,
            "port": self.port,
            "session_log": self.session_log,
            "fast_cli": False,
        }

        ssh_conn = SSHDetect(**autodetect_ssh_conn_params)
        netdev_os_best_match = ssh_conn.autodetect()
        ssh_conn.connection.disconnect()

        return netdev_os_best_match

    def connect(self):
        """Establishes a SSH connection to the device and returns it."""

        if self.device_type:
            device_type = self.device_type
        else:
            device_type = self.get_netdev_os()

        ssh_conn_params = {
            "device_type": device_type,
            "host": self.netdev_host,
            "username": self.__username,
            "password": self.__password,
            "secret": self._secret,
            "port": self.port,
            "session_log": self.session_log,
            "fast_cli": False,
        }

        self.ssh_conn = ConnectHandler(**ssh_conn_params)
        return self.ssh_conn

    def disconnect(self):
        """Disconnects the SSH connection to the device."""
        print(self.ssh_conn)

        if self.ssh_conn.check_config_mode():
            self.ssh_conn.exit_config_mode()

        if self.ssh_conn.is_alive():
            self.ssh_conn.disconnect()
