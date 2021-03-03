# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import copy
import ipaddress
import time

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.gateway as vcd_gateway

import container_service_extension.cloudapi.constants as cloudapi_constants
from container_service_extension.logger import SERVER_LOGGER
import container_service_extension.pyvcloud_utils as pyvcloud_utils
import container_service_extension.server_constants as server_constants
from container_service_extension.server_constants import NsxtGatewayRequestKey
from container_service_extension.server_constants import NsxtNATRuleKey
import container_service_extension.shared_constants as shared_constants
from container_service_extension.shared_constants import PaginationKey
import container_service_extension.utils as server_utils


def _get_available_subnet_info(subnet_values, network_to_available_ip_dict):
    """Get subnet with available ips.

    :param arr subnet_values: array of dicts containing subnet info
    :param dict network_to_available_ip_dict: dict mapping
        (gateway_ip, prefix_length) to available ip count

    :return: subnet value index, subnet gateway ip, subnet prefix length.
        An index of -1 is returned if no subnet has available ips.
    """
    # Get external network
    for index, subnet in enumerate(subnet_values):
        gateway_ip = subnet[NsxtGatewayRequestKey.GATEWAY]
        prefix_length = subnet[NsxtGatewayRequestKey.PREFIX_LENGTH]
        available_ip_count = network_to_available_ip_dict. \
            get((gateway_ip, prefix_length), 0)
        if available_ip_count > 0:
            return index, gateway_ip, prefix_length
    return -1, None, None


def _get_updated_subnet_value(updated_get_gateway_response, gateway_ip,
                              prefix_length):
    """Get the updated subnet value given the updated gateway response."""
    updated_subnet_values = _gateway_body_to_subnet_values(updated_get_gateway_response)  # noqa: E501
    for subnet in updated_subnet_values:
        if subnet[NsxtGatewayRequestKey.GATEWAY] == gateway_ip and \
                subnet[NsxtGatewayRequestKey.PREFIX_LENGTH] == prefix_length:
            return subnet
    return None


def _gateway_body_to_external_address_id(gateway_body: dict):
    return gateway_body[NsxtGatewayRequestKey.EDGE_GATEWAY_UPLINKS][
        server_constants.NSXT_BACKED_GATEWAY_UPLINK_INDEX][NsxtGatewayRequestKey.UPLINK_ID]  # noqa: E501


def _gateway_body_to_subnet_values(gateway_body: dict):
    """Get subnet values from gateway body.

    :param dict gateway_body: body from get response for gateways endpoint

    :return: list of  subnet value dictionaries
    :rtype: list
    """
    return gateway_body[NsxtGatewayRequestKey.EDGE_GATEWAY_UPLINKS][
        server_constants.NSXT_BACKED_GATEWAY_UPLINK_INDEX][
        NsxtGatewayRequestKey.SUBNETS][NsxtGatewayRequestKey.VALUES]


def _subnet_value_to_ip_ranges(subnet_value: dict):
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


def _get_ip_address_difference(updated_subnet_value, orig_subnet_value):
    updated_ip_ranges = _subnet_value_to_ip_ranges(updated_subnet_value)
    orig_ip_ranges = _subnet_value_to_ip_ranges(orig_subnet_value)

    updated_ip_range_set = _get_ip_range_set(updated_ip_ranges)
    orig_ip_range_set = _get_ip_range_set(orig_ip_ranges)

    return list(updated_ip_range_set - orig_ip_range_set)


class NsxtBackedGatewayService:
    """Service functions for an NSX-T backed Edge Gateway."""

    def __init__(self, gateway: vcd_gateway.Gateway,
                 client: vcd_client.Client):
        assert gateway.is_nsxt_backed()

        self._gateway = gateway
        self._client = client
        self._cloudapi_client = \
            pyvcloud_utils.get_cloudapi_client_from_vcd_client(client)
        gateway_id = server_utils.extract_id_from_href(self._gateway.href)
        self._gateway_urn = f'{server_constants.GATEWAY_URN_PREFIX}:' \
                            f'{gateway_id}'
        gateway_relative_path = \
            f'{cloudapi_constants.CloudApiResource.EDGE_GATEWAYS}/' \
            f'{self._gateway_urn}'
        self._gateway_relative_path = gateway_relative_path
        self._nat_rules_relative_path = \
            f'{gateway_relative_path}/{server_constants.NATS_PATH_FRAGMENT}/' \
            f'{server_constants.RULES_PATH_FRAGMENT}'

    def quick_ip_allocation(self):
        """Allocate one ip using the edge quick ip allocation feature."""
        # Get current edge gateway body to use for PUT request body
        put_request_body = self._get_gateway()

        # Edit PUT request body
        subnet_values = _gateway_body_to_subnet_values(put_request_body)
        external_network_id = _gateway_body_to_external_address_id(put_request_body)  # noqa: E501
        network_to_available_ip_dict = self._get_external_network_available_ip_dict(external_network_id)  # noqa: E501
        subnet_index, gateway_ip, prefix_length = _get_available_subnet_info(subnet_values, network_to_available_ip_dict)  # noqa: E501
        if subnet_index == -1:
            raise Exception('No subnet found with available ips)')
        request_subnet_value = subnet_values[subnet_index]
        orig_subnet_value = copy.deepcopy(request_subnet_value)
        request_subnet_value[NsxtGatewayRequestKey.TOTAL_IP_COUNT] = \
            int(request_subnet_value[NsxtGatewayRequestKey.TOTAL_IP_COUNT]) + 1
        request_subnet_value[NsxtGatewayRequestKey.AUTO_ALLOCATE_IP_RANGES] = True  # noqa: E501

        # Sent request for quick ip allocation
        self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.PUT,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=self._gateway_relative_path,
            payload=put_request_body,
            content_type='application/json')

        # Ensure gateway response status is realized
        while True:
            updated_get_gateway_response = self._get_gateway()
            if updated_get_gateway_response[NsxtGatewayRequestKey.STATUS] != \
                    server_constants.NSXT_GATEWAY_REALIZED_STATUS:
                time.sleep(server_constants.NSXT_PUT_REQUEST_WAIT_TIME)
            else:
                break

        # Determine quick ip allocated address
        updated_subnet_value = _get_updated_subnet_value(
            updated_get_gateway_response, gateway_ip, prefix_length)
        if not updated_subnet_value:
            raise Exception(f'Updated subnet value with gateway '
                            f'({gateway_ip}) and prefix length '
                            f'({prefix_length}) not found')
        ip_address_diff = _get_ip_address_difference(updated_subnet_value,
                                                     orig_subnet_value)
        if not ip_address_diff:
            return None
        return ip_address_diff[0]

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
            server_constants.NsxtNATRuleKey.NAME: name,
            server_constants.NsxtNATRuleKey.DESCRIPTION: description,
            server_constants.NsxtNATRuleKey.ENABLED: enabled,
            server_constants.NsxtNATRuleKey.RULE_TYPE: server_constants.DNAT_RULE_TYPE,  # noqa: E501
            server_constants.NsxtNATRuleKey.EXTERNAL_ADDRESSES: external_address,  # noqa: E501
            server_constants.NsxtNATRuleKey.INTERNAL_ADDRESSES: internal_address,  # noqa: E501
            server_constants.NsxtNATRuleKey.LOGGING: logging_enabled,
            server_constants.NsxtNATRuleKey.APPLICATION_PORT_PROFILE:
                application_port_profile,
            server_constants.NsxtNATRuleKey.DNAT_EXTERNAL_PORT: dnat_external_port  # noqa: E501
        }

        self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.POST,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=self._nat_rules_relative_path,
            payload=post_body,
            content_type='application/json')

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
            f'{external_network_id}/{server_constants.AVAILABLE_IP_PATH_FRAGMENT}'  # noqa: E501
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
            return

        try:
            self._cloudapi_client.do_request(
                method=shared_constants.RequestMethod.DELETE,
                cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,  # noqa: E501
                resource_url_relative_path=f"{self._nat_rules_relative_path}/{nat_rule_id}")  # noqa: E501
            delete_response = self._cloudapi_client.get_last_response()
            task_href = delete_response.headers._store['location'][1]
            task_monitor = self._client.get_task_monitor()
            task = task_monitor._get_task_status(task_href)
            task_monitor.wait_for_status(task)
        except Exception as err:
            SERVER_LOGGER.info(f'Failed to delete dnat rule: {str(err)}')
            return

    def _get_dnat_rule_id(self, rule_name):
        try:
            nat_rules = self._list_nat_rules()
        except Exception:
            return None

        for nat_rule in nat_rules:
            if nat_rule[NsxtNATRuleKey.NAME] == rule_name:
                return nat_rule[NsxtNATRuleKey.ID]
        return None

    def _get_nat_rules_response(self,
                                page_num=server_constants.DEFAULT_FIRST_PAGE,
                                page_size=server_constants.NAT_DEFAULT_PAGE_SIZE):  # noqa: E501
        nat_rules_query_path = f"{self._nat_rules_relative_path}?" \
                               f"{PaginationKey.PAGE_NUMBER}={page_num}" \
                               f"&{PaginationKey.PAGE_SIZE}={page_size}"
        return self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=nat_rules_query_path)

    def _list_nat_rules(self):
        """List nat rule dictionaries.

        :return: Generator of nat rule dictionaries.
        :rtype: Generator[dict]
        """
        page_num = 0
        while True:
            page_num += 1
            response_body = self._get_nat_rules_response(
                page_num=page_num,
                page_size=server_constants.NAT_DEFAULT_PAGE_SIZE)
            values = response_body[PaginationKey.VALUES]
            if len(values) == 0:
                break
            for nat_rule in values:
                yield nat_rule
