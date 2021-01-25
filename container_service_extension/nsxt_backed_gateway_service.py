# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.gateway as vcd_gateway

import container_service_extension.cloudapi.constants as cloudapi_constants
import container_service_extension.pyvcloud_utils as pyvcloud_utils
import container_service_extension.server_constants as server_constants
import container_service_extension.shared_constants as shared_constants
import container_service_extension.utils as server_utils


def _get_uplink_index(uplinks, uplink_name):
    """Get the index in the uplinks array of the correct uplink name.
    :param arr uplinks: array of uplinks
    :param str uplink_name: name of the uplink
    :return: index of the uplink. -1 is returned if the uplink name is not
        found.
    :rtype: int
    """
    for index, uplink in enumerate(uplinks):
        if uplink['uplinkName'] == uplink_name:
            return index
    return -1


def _get_subnet_index(gateway, prefix_length, subnet_values):
    """Get the index in the subnet values array of the correct subnet dict.

    :param str gateway: ip of the subnet
    :param int prefix_length: prefix length of the subnet
    :param arr subnet_values: array of dicts containing subnet info
    :return: index of the target gateway. -1 is returned if the uplink name
        is not found.
    :rtype: int
    """
    for index, subnet in enumerate(subnet_values):
        if subnet['gateway'] == gateway and \
                subnet['prefixLength'] == prefix_length:
            return index
    return -1


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
        self._gateway_urn = f'{server_constants.GATEWAY_URN_PREFIX}' \
                            f'{gateway_id}'

    def quick_ip_allocation(self, external_network_name, gateway_ip,
                            prefix_length, number_ips):
        """Allocate an ip using the edge quick ip allocation feature.

        :param str gateway_ip: ip of the subnet
        :param int prefix_length: prefix length of the subnet
        :param int number_ips: number of ips to allocate
        """

        # Get current edge gateway body and use for PUT request body
        gateway_relative_path = \
            f'{cloudapi_constants.CloudApiResource.EDGE_GATEWAYS}/' \
            f'{self._gateway_urn}'
        put_request_body = self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=gateway_relative_path)

        # Edit PUT request body
        uplink_index = _get_uplink_index(
            put_request_body['edgeGatewayUplinks'],
            external_network_name)
        if uplink_index == -1:
            raise Exception(f'No uplink found with name '
                            f'({external_network_name})')
        subnet_values = \
            put_request_body['edgeGatewayUplinks'][uplink_index]['subnets']['values']  # noqa: E501
        subnet_index = _get_subnet_index(gateway_ip, prefix_length,
                                         subnet_values)
        if subnet_index == -1:
            raise Exception(f'No subnet found with gateway ip ({gateway_ip}) '
                            f'and prefix length ({prefix_length})')
        request_subnet_value = subnet_values[subnet_index]
        request_subnet_value["totalIpCount"] = \
            int(request_subnet_value["totalIpCount"]) + number_ips
        request_subnet_value["autoAllocateIpRanges"] = True

        self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.PUT,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=gateway_relative_path,
            payload=put_request_body,
            content_type='application/json')

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

        nat_rules_relative_path = \
            f'{cloudapi_constants.CloudApiResource.EDGE_GATEWAYS}/' \
            f'{self._gateway_urn}{server_constants.NATS_PATH}' \
            f'{server_constants.RULES_PATH}'
        self._cloudapi_client.do_request(
            method=shared_constants.RequestMethod.POST,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=nat_rules_relative_path,
            payload=post_body,
            content_type='application/json')
