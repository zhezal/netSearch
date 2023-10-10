"""Class for getting basic data from network equipment."""

__author__ = "ZHEZLYAEV Aleksandr  <zhezlyaev@gmail.com>"
__version__ = "1.0"

# -*- coding: utf-8 -*-


class UnsupportedOsType(Exception):
    """Exception class is generated when the operating system is not supported
    by the parser."""

    def __init__(self, *args):
        self.message = args[0] if args else "Undefined error."

    def __str__(self):
        return f"Error: {self.message}"


class NetworkParsingError(Exception):
    """An exception is generated when data from the device was received, but
    the parser could not process them."""

    def __init__(self, *args):
        self.message = args[0] if args else "Undefined error."

    def __str__(self):
        return f"Error: {self.message}"


class BaseNetTools:
    """Class for getting basic data from network equipment."""

    def __init__(self, ssh_conn) -> None:
        self.ssh_conn = ssh_conn

    def __repr__(self):
        return f"{self.__class__}"

    def __str__(self):
        return f"{self.__class__.__name__}"

    def get_all_vlan_info(self) -> list[dict]:
        """The method collects information about all vlan id/vlan name from
        network devices."""

        cisco_nxos_show_vlan_template = "ntc_templates/cisco_nxos_show_vlan.textfsm"

        if self.ssh_conn.device_type == "cisco_nxos":
            show_vlan = self.ssh_conn.send_command(
                "show vlan", use_textfsm=True, textfsm_template=cisco_nxos_show_vlan_template
            )

            if not isinstance(show_vlan, list):
                raise UnsupportedOsType(f"{self.__class__} {self.ssh_conn.host} OS isn't supported.")

        return show_vlan

    def get_ip_interface(self, vlan_id):
        cisco_nxos_show_ip_interface_template = "ntc_templates/cisco_nxos_show_ip_interface.textfsm"

        if self.ssh_conn.device_type == "cisco_nxos":
            show_ip_interface = self.ssh_conn.send_command(
                f"sh ip int vlan {vlan_id}",
                use_textfsm=True,
                textfsm_template=cisco_nxos_show_ip_interface_template,
            )

            if not isinstance(show_ip_interface, list):
                raise UnsupportedOsType(f"{self.__class__} {self.ssh_conn.host} OS isn't supported.")

        return show_ip_interface

    def get_interface(self, vlan_id):
        cisco_nxos_show_interface_template = "ntc_templates/cisco_nxos_show_interface.textfsm"

        if self.ssh_conn.device_type == "cisco_nxos":
            show_interface = self.ssh_conn.send_command(
                f"show interface vlan {vlan_id}",
                use_textfsm=True,
                textfsm_template=cisco_nxos_show_interface_template,
            )

            if not isinstance(show_interface, list):
                raise UnsupportedOsType(f"{self.__class__} {self.ssh_conn.host} OS isn't supported.")

        return show_interface

    def get_ip_arp(self, intf, vrf):
        cisco_nxos_show_ip_arp_template = "ntc_templates/cisco_nxos_show_ip_arp.textfsm"

        if self.ssh_conn.device_type == "cisco_nxos":
            show_ip_arp = self.ssh_conn.send_command(
                f"show ip arp {intf} vrf {vrf}",
                use_textfsm=True,
                textfsm_template=cisco_nxos_show_ip_arp_template,
            )

            if not isinstance(show_ip_arp, list):
                raise UnsupportedOsType(f"{self.__class__} {self.ssh_conn.host} OS isn't supported.")

        return show_ip_arp
