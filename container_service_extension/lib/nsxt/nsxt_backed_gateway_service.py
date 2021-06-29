# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import ipaddress

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.gateway as vcd_gateway

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.common.constants.shared_constants import PaginationKey  # noqa: E501
import container_service_extension.common.utils.core_utils as core_utils
import container_service_extension.common.utils.pyvcloud_utils as pyvcloud_utils  # noqa: E501
import container_service_extension.lib.cloudapi.constants as cloudapi_constants
import container_service_extension.lib.nsxt.constants as nsxt_constants
from container_service_extension.lib.nsxt.constants import \
    NsxtGatewayRequestKey, NsxtNATRuleKey
from container_service_extension.logging.logger import SERVER_LOGGER


def _gateway_body_to_subnet_values(gateway_body: dict):
    """Get subnet values from gateway body.

    :param dict gateway_body: body from get response for gateways endpoint

    :return: list of  subnet value dictionaries
    :rtype: list
    """
    return gateway_body[NsxtGatewayRequestKey.EDGE_GATEWAY_UPLINKS][
        nsxt_constants.NSXT_BACKED_GATEWAY_UPLINK_INDEX][
        NsxtGatewayRequestKey.SUBNETS][NsxtGatewayRequestKey.VALUES]


def _subnet_value_to_ip_ranges_values(subnet_value: dict):
    return subnet_value[NsxtGatewayRequestKey.IP_RANGES][NsxtGatewayRequestKey.VALUES]  # noqa: E501


def _get_ip_range_set(ip_ranges: list):
    """Get set of ip addresses.

    :param list ip_ranges: list of dictionaries, each containing a start and
        end ip address

    :return: set of ip addresses
    :rtype: set
    """
    ip_range_set = set()
    for ip_range in ip_ranges:
        start_ip = ipaddress.ip_address(ip_range[NsxtGatewayRequestKey.START_ADDRESS])  # noqa: E501
        end_ip = ipaddress.ip_address(ip_range[NsxtGatewayRequestKey.END_ADDRESS])  # noqa: E501

        # Add to ip range set
        curr_ip = start_ip
        while curr_ip <= end_ip:
            ip_range_set.add(format(curr_ip))
            curr_ip += 1
    return ip_range_set


def _get_available_ip_in_ip_ranges(ip_ranges: list, used_ips: set):
    """Get an available ip from the passed in ip ranges.

    :param list ip_ranges: list of dictionaries, each containing a start and
        end ip address
    :param set used_ips: set of used ips.


    :return: available ip. Empty string returned if no available ip.
    :rtype: str
    """
    for ip_range in ip_ranges:
        start_ip = ipaddress.ip_address(ip_range[NsxtGatewayRequestKey.START_ADDRESS])  # noqa: E501
        end_ip = ipaddress.ip_address(ip_range[NsxtGatewayRequestKey.END_ADDRESS])  # noqa: E501

        # Search through ips
        curr_ip = start_ip
        while curr_ip <= end_ip:
            curr_ip_str = format(curr_ip)
            if curr_ip_str not in used_ips:
                return curr_ip_str
            curr_ip += 1
    return None


class NsxtBackedGatewayService:
    """Service functions for an NSX-T backed Edge Gateway."""

    def __init__(self, gateway: vcd_gateway.Gateway,
                 client: vcd_client.Client):
        assert gateway.is_nsxt_backed()

        self._gateway = gateway
        self._client = client
        self._cloudapi_client = \
            pyvcloud_utils.get_cloudapi_client_from_vcd_client(client)
        gateway_id = core_utils.extract_id_from_href(self._gateway.href)
        self._gateway_urn = f'{nsxt_constants.GATEWAY_URN_PREFIX}:' \
                            f'{gateway_id}'
        gateway_relative_path = \
            f'{cloudapi_constants.CloudApiResource.EDGE_GATEWAYS}/' \
            f'{self._gateway_urn}'
        self._gateway_relative_path = gateway_relative_path
        self._nat_rules_relative_path = \
            f'{gateway_relative_path}/{nsxt_constants.NATS_PATH_FRAGMENT}/' \
            f'{nsxt_constants.RULES_PATH_FRAGMENT}'

    def add_dnat_rule(self,
                      name,
                      internal_address,
                      external_address,
                      dnat_external_port=None,
                      description='',
                      logging_enabled=False,
                      enabled=True,
                      application_port_profile=None):
        """Add a DNAT rule for an NSX-T backed gateway.

        :param str name: name of the rule
        :param str internal address: internal ip address
        :param str external address: external ip address
        :param int dnat_external_port: external port
        :param str description: rule description
        :param bool logging_enabled: indicate if logging is enabled
        :param bool enabled: indicate state
        :param dict application_port_profile: dict with keys "id" and "name"
            for port profile
        """
        post_body = {
            NsxtNATRuleKey.NAME: name,
            NsxtNATRuleKey.DESCRIPTION: description,
            NsxtNATRuleKey.ENABLED: enabled,
            NsxtNATRuleKey.RULE_TYPE: nsxt_constants.DNAT_RULE_TYPE,
            NsxtNATRuleKey.EXTERNAL_ADDRESSES: external_address,
            NsxtNATRuleKey.INTERNAL_ADDRESSES: internal_address,
            NsxtNATRuleKey.LOGGING: logging_enabled,
            NsxtNATRuleKey.APPLICATION_PORT_PROFILE: application_port_profile,
            NsxtNATRuleKey.DNAT_EXTERNAL_PORT: dnat_external_port
        }

        try:
            self._cloudapi_client.do_request(
                method=shared_constants.RequestMethod.POST,
                cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,  # noqa: E501
                resource_url_relative_path=self._nat_rules_relative_path,
                payload=post_body,
                content_type='application/json')
            self._wait_for_last_cloudapi_task()
        except Exception as err:
            SERVER_LOGGER.info(f'Error when creating dnat rule: {err}')
            raise

    def _wait_for_last_cloudapi_task(self):
        """Wait for last cloudapi task.

        :raises VcdException if there is a failed task
        """
        last_cloudapi_response = self._cloudapi_client.get_last_response()
        task_href = last_cloudapi_response.headers._store['location'][1]
        task_monitor = self._client.get_task_monitor()
        task = task_monitor._get_task_status(task_href)
        task_monitor.wait_for_status(task)

    def _get_gateway(self):
        return self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=self._gateway_relative_path)

    def _get_external_network_available_ip_dict(self, external_network_id):
        """Form dict of network info to number available ips.

        :return: dict mapping (gateway_ip, prefix_length) to number available
            ips.
        """
        request_relative_path = \
            f'{cloudapi_constants.CloudApiResource.EXTERNAL_NETWORKS}/' \
            f'{external_network_id}/{nsxt_constants.AVAILABLE_IP_PATH_FRAGMENT}'  # noqa: E501
        available_ip_response = self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=request_relative_path)

        network_to_available_ip_dict = {}
        for available_ip_value in available_ip_response['values']:
            gateway_ip = available_ip_value[NsxtGatewayRequestKey.GATEWAY]
            prefix_length = available_ip_value[NsxtGatewayRequestKey.PREFIX_LENGTH]  # noqa: E501
            available_ip_count = available_ip_value[NsxtGatewayRequestKey.TOTAL_IP_COUNT]  # noqa: E501
            network_to_available_ip_dict[(gateway_ip, prefix_length)] = int(available_ip_count)  # noqa: E501
        return network_to_available_ip_dict

    def delete_dnat_rule(self, rule_name):
        nat_rule_id = self._get_dnat_rule_id(rule_name)
        if not nat_rule_id:
            raise Exception(f'No dnat rule found with name: {rule_name}')

        try:
            self._cloudapi_client.do_request(
                method=shared_constants.RequestMethod.DELETE,
                cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,  # noqa: E501
                resource_url_relative_path=f"{self._nat_rules_relative_path}/{nat_rule_id}")  # noqa: E501
            self._wait_for_last_cloudapi_task()
        except Exception as err:
            SERVER_LOGGER.info(f'Failed to delete dnat rule: {str(err)}')

    def _get_dnat_rule_id(self, rule_name):
        """Get dnat rule id.

        :param str rule_name: dnat rule name

        :return: rule id
        :rtype: str
        """
        try:
            nat_rules = self._list_nat_rules()
        except Exception:
            return None

        for nat_rule in nat_rules:
            if nat_rule[NsxtNATRuleKey.NAME] == rule_name:
                return nat_rule[NsxtNATRuleKey.ID]
        return None

    def _get_nat_rules_response(self,
                                cursor=None,
                                page_size=server_constants.NAT_DEFAULT_PAGE_SIZE):  # noqa: E501
        """Get the nat rules response.

        :param str cursor: cursor param for the next page.
        :param int page_size: page size

        :return: response body, cursor
        :rtype: tuple
        """
        nat_rules_query_path = f'{self._nat_rules_relative_path}?' \
                               f'{PaginationKey.PAGE_SIZE}={page_size}'
        if cursor:
            nat_rules_query_path += f'&{PaginationKey.CURSOR}={cursor}'
        response_body = self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=nat_rules_query_path)
        cursor = self._cloudapi_client.get_cursor_param()
        return response_body, cursor

    def _list_nat_rules(self):
        """List nat rule dictionaries.

        :return: Generator of nat rule dictionaries.
        :rtype: Generator[dict]
        """
        cursor = None
        while True:
            response_body, cursor = self._get_nat_rules_response(
                cursor=cursor,
                page_size=server_constants.NAT_DEFAULT_PAGE_SIZE)
            values = response_body[PaginationKey.VALUES]
            if len(values) == 0:
                break
            for nat_rule in values:
                yield nat_rule
            if not cursor:
                break

    def _get_used_ip_addresses_response(self,
                                        page_num=server_constants.DEFAULT_FIRST_PAGE,  # noqa: E501
                                        page_size=server_constants.USED_IP_ADDRESS_PAGE_SIZE):  # noqa:E 501
        used_ip_address_path = \
            f'{self._gateway_relative_path}/' \
            f'{cloudapi_constants.CloudApiResource.USED_IP_ADDRESSES}?' \
            f'{PaginationKey.PAGE_NUMBER}={page_num}&' \
            f'{PaginationKey.PAGE_SIZE}={page_size}'
        return self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=used_ip_address_path)

    def _list_used_ip_addresses(self):
        """List ip addresses.

        :return: Generator of ip addresses.
        :rtype: Generator[str]
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self._get_used_ip_addresses_response(
                page_num=page_num,
                page_size=server_constants.USED_IP_ADDRESS_PAGE_SIZE)
            values = response_body[PaginationKey.VALUES]
            if len(values) == 0:
                break
            for used_ip_value_dict in values:
                yield used_ip_value_dict[NsxtGatewayRequestKey.IP_ADDRESS]

    def get_available_ip(self) -> str:
        """Get an available ip.

        :return: available ip.
        :rtype: str
        """
        # Get all used ips
        used_ips: set = {used_ip for used_ip in self._list_used_ip_addresses()}

        # Iterate through ip ranges and find first available ip
        get_gateway_response = self._get_gateway()
        subnet_values = _gateway_body_to_subnet_values(get_gateway_response)
        for subnet_value in subnet_values:
            ip_ranges: list = _subnet_value_to_ip_ranges_values(subnet_value)
            available_ip = _get_available_ip_in_ip_ranges(ip_ranges, used_ips)
            if available_ip:
                return available_ip
        return None
