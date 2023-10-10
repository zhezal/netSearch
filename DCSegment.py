# -*- coding: utf-8 -*-

"""Date class for the cli_dc_segment_info app."""

__author__ = "ZHEZLYAEV Aleksandr  <zhezlyaev@gmail.com>"
__version__ = "1.0"

import ipaddress
from dataclasses import dataclass, field


@dataclass
class DCSegment:
    """Data class for storing DC network segment parameters."""

    vlan_id: int
    vrf_name: str
    segment_description: str
    num_of_all_active_hosts: int
    num_of_network_service_hosts: int
    networks: list = field(default_factory=list)
    vlan_dc: list = field(default_factory=list)
    hosts_in_segment: list = field(default_factory=list)

    num_of_active_hosts: int = field(init=False)
    free_address_for_hosts: int = field(init=False)
    net_usage_in_percentage: float = field(init=False)

    def __post_init__(self):
        # количество активных клиентов
        self.num_of_active_hosts = self.num_of_all_active_hosts - self.num_of_network_service_hosts

        # количество свободных адресов для клиентов
        possible_num_of_addresses_in_net = 0
        for network in self.networks:
            IPNetwork = ipaddress.IPv4Network(network)
            possible_num_of_addresses_in_net = possible_num_of_addresses_in_net + (IPNetwork.num_addresses - 2)
        self.free_address_for_hosts = (
            possible_num_of_addresses_in_net - self.num_of_network_service_hosts - self.num_of_active_hosts
        )

        # Использование сети в %
        self.net_usage_in_percentage = round(
            (self.num_of_active_hosts * 100) / (possible_num_of_addresses_in_net - self.num_of_network_service_hosts), 2
        )

    def __eq__(self, other):
        self.net_usage_in_percentage == other.net_usage_in_percentage
