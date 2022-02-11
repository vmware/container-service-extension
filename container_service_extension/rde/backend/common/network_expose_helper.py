# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import re

import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.exceptions import EntityNotFoundException, MultipleRecordsException  # noqa: E501
import pyvcloud.vcd.gateway as vcd_gateway

from container_service_extension.common.constants.server_constants import CSE_CLUSTER_KUBECONFIG_PATH  # noqa: E501
from container_service_extension.common.constants.server_constants import EXPOSE_CLUSTER_NAME_FRAGMENT  # noqa: E501
from container_service_extension.common.constants.server_constants import IP_PORT_REGEX  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.lib.cloudapi.constants as cloudapi_constants
from container_service_extension.lib.nsxt.nsxt_backed_gateway_service import NsxtBackedGatewayService  # noqa: E501
from container_service_extension.logging.logger import NULL_LOGGER
from container_service_extension.logging.logger import SERVER_CLOUDAPI_WIRE_LOGGER  # noqa: E501
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER


def _get_gateway(
        client: vcd_client.Client,
        org_name: str,
        network_name: str,
):
    config = server_utils.get_server_runtime_config()
    logger_wire = NULL_LOGGER
    if utils.str_to_bool(config.get_value_at('service.log_wire')):
        logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER
    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(
        client=client,
        logger_debug=LOGGER,
        logger_wire=logger_wire
    )

    gateway_name, gateway_href, gateway_exists = None, None, False
    page, page_count = 1, 1
    base_path = f'{cloudapi_constants.CloudApiResource.ORG_VDC_NETWORKS}?filter=name=={network_name};_context==includeAccessible&pageSize=1&page='  # noqa: E501

    while page <= page_count:
        response, headers = cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=base_path + f'{page}',
            return_response_headers=True)
        for entry in response['values']:
            # only routed networks allowed
            is_target_network = entry['orgRef']['name'] == org_name and \
                entry['networkType'] == 'NAT_ROUTED'
            if is_target_network:
                if gateway_exists:
                    raise MultipleRecordsException(f"Multiple routed networks named {network_name} found. CSE Server expects unique network names.")  # noqa: E501
                gateway_exists = True
                gateway_name = entry['connection']['routerRef']['name']
                gateway_id = entry['connection']['routerRef']['id'].split(':').pop()  # noqa: E501
                gateway_href = headers['Content-Location'].split('cloudapi')[0] + f'api/admin/edgeGateway/{gateway_id}'  # noqa: E501
        page += 1
        page_count = response['pageCount']

    if not gateway_exists:
        raise EntityNotFoundException(f"No routed networks named {network_name} found.")  # noqa: E501

    gateway = vcd_gateway.Gateway(client, name=gateway_name, href=gateway_href)
    return gateway


def _get_nsxt_backed_gateway_service(client: vcd_client.Client, org_name: str,
                                     network_name: str):
    # Check if NSX-T backed gateway
    gateway: vcd_gateway.Gateway = _get_gateway(
        client=client,
        org_name=org_name,
        network_name=network_name)
    if not gateway:
        raise Exception(f'No gateway found for network: {network_name}')
    if not gateway.is_nsxt_backed():
        raise Exception('Gateway is not NSX-T backed for exposing cluster.')

    config = server_utils.get_server_runtime_config()
    logger_wire = NULL_LOGGER
    if utils.str_to_bool(config.get_value_at('service.log_wire')):
        logger_wire = SERVER_CLOUDAPI_WIRE_LOGGER
    return NsxtBackedGatewayService(
        gateway=gateway,
        client=client,
        logger_debug=LOGGER,
        logger_wire=logger_wire
    )


def construct_init_cluster_script_with_exposed_ip(script: str, expose_ip: str):
    """Construct init cluster script with expose ip control plane endpoint option.

    If the '--control-plane-endpoint' option is already present, this option
    will be replaced with this option specifying the exposed ip. If this option
    is not specified, the '--control-plane-endpoint' option will be added.

    :param str script: the init cluster script
    :param str expose_ip: the ip to expose the cluster

    :return: the updated init cluster script
    :rtype: str
    """
    # Get line with 'kubeadm init'
    kubeadm_init_match: re.Match = re.search('kubeadm init .+\n', script)
    if not kubeadm_init_match:
        return script
    kubeadm_init_line: str = kubeadm_init_match.group(0)

    # Either add or replace the control plane endpoint option
    expose_control_plane_endpoint_option = f'--control-plane-endpoint=\"{expose_ip}:6443\"'  # noqa: E501
    expose_kubeadm_init_line = re.sub(
        f'--control-plane-endpoint={IP_PORT_REGEX}',
        expose_control_plane_endpoint_option,
        kubeadm_init_line)
    if kubeadm_init_line == expose_kubeadm_init_line:  # no option was replaced
        expose_kubeadm_init_line = kubeadm_init_line.replace(
            'kubeadm init',
            f'kubeadm init --control-plane-endpoint=\"{expose_ip}:6443\"')

    # Replace current kubeadm init line with line containing expose_ip
    return script.replace(kubeadm_init_line, expose_kubeadm_init_line)


def construct_expose_dnat_rule_name(cluster_name: str, cluster_id: str):
    """Construct dnat rule name for exposed cluster.

    Dnat rule name includes cluster name to show users the cluster rule
    corresponds to. The cluster id is used to make the rule unique
    """
    return f"{cluster_name}_{cluster_id}_{EXPOSE_CLUSTER_NAME_FRAGMENT}"


def construct_script_to_update_kubeconfig_with_internal_ip(
        kubeconfig_with_exposed_ip: str, internal_ip: str):
    """Construct script to update kubeconfig file with internal ip.

    :param dict kubeconfig_with_exposed_ip: the current kubeconfig
    :param str internal_ip: the internal ip of the control plane node

    :return: the script that will replace external ip in kubeconfig with
        internal ip

    :rtype: str
    """
    kubeconfig_with_internal_ip = get_updated_kubeconfig_with_internal_ip(
        kubeconfig_with_exposed_ip, internal_ip
    )
    script = f"#!/usr/bin/env bash\n" \
             f"echo \'{kubeconfig_with_internal_ip}\' > " \
             f"{CSE_CLUSTER_KUBECONFIG_PATH}\n"
    return script


def get_updated_kubeconfig_with_internal_ip(
        kubeconfig_with_exposed_ip,
        internal_ip: str):
    return re.sub(
        pattern=IP_PORT_REGEX,
        repl=f'{internal_ip}:6443',
        string=str(kubeconfig_with_exposed_ip)
    )


def expose_cluster(client: vcd_client.Client, org_name: str,
                   network_name: str, cluster_name: str, cluster_id: str,
                   internal_ip: str):
    """Create DNAT rule to expose a cluster.

    Get a free static IP from the edge gateway powering the Org VDC network,
        and create a DNAT rule to expose the @internal_ip

    :param vcd_client.Client client:
    :param str org_name:
    :param str network_name:
    :param str cluster_name:
    :param str cluster_id:
    :param str internal_ip:

    :raises Exception: If CSE is unable to get a free IP or add the DNAT rule.

    :returns: The newly acquired exposed Ip of the cluster

    :rtype: str
    """
    # Auto reserve ip and add dnat rule
    nsxt_gateway_svc = _get_nsxt_backed_gateway_service(
        client, org_name, network_name)
    expose_ip = nsxt_gateway_svc.get_available_ip()
    if not expose_ip:
        raise Exception(f'No available ips found for cluster {cluster_name} ({cluster_id})')  # noqa: E501
    try:
        dnat_rule_name = construct_expose_dnat_rule_name(
            cluster_name, cluster_id
        )
        nsxt_gateway_svc.add_dnat_rule(
            name=dnat_rule_name,
            internal_address=internal_ip,
            external_address=expose_ip)
    except Exception as err:
        raise Exception(f"Unable to add dnat rule with error: {str(err)}")
    return expose_ip


def handle_delete_expose_dnat_rule(client: vcd_client.Client,
                                   org_name: str,
                                   network_name: str,
                                   cluster_name: str,
                                   cluster_id: str):
    """Delete DNAT rule that exposes a cluster.

    :param vcd_client.Client client:
    :param str org_name:
    :param str network_name:
    :param str cluster_name:
    :param str cluster_id:

    :returns: Nothing
    """
    nsxt_gateway_svc = _get_nsxt_backed_gateway_service(
        client, org_name, network_name
    )
    expose_dnat_rule_name = construct_expose_dnat_rule_name(
        cluster_name, cluster_id
    )
    nsxt_gateway_svc.delete_dnat_rule(expose_dnat_rule_name)
