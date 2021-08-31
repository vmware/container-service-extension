# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import re

import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.exceptions import EntityNotFoundException
import pyvcloud.vcd.gateway as vcd_gateway
from pyvcloud.vcd.vdc import VDC
import pyvcloud.vcd.vdc_network as vdc_network

from container_service_extension.common.constants.server_constants import CSE_CLUSTER_KUBECONFIG_PATH  # noqa: E501
from container_service_extension.common.constants.server_constants import EXPOSE_CLUSTER_NAME_FRAGMENT  # noqa: E501
from container_service_extension.common.constants.server_constants import IP_PORT_REGEX  # noqa: E501
from container_service_extension.common.constants.server_constants import NETWORK_URN_PREFIX  # noqa: E501
from container_service_extension.common.constants.server_constants import VdcNetworkInfoKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.lib.cloudapi.constants as cloudapi_constants
from container_service_extension.lib.nsxt.nsxt_backed_gateway_service import NsxtBackedGatewayService  # noqa: E501
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER


def _get_vdc_network_response(cloudapi_client, network_urn_id: str):
    relative_path = f'{cloudapi_constants.CloudApiResource.ORG_VDC_NETWORKS}' \
                    f'?filter=id=={network_urn_id}'
    response = cloudapi_client.do_request(
        method=RequestMethod.GET,
        cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
        resource_url_relative_path=relative_path)
    return response


def _get_gateway_href(vdc: VDC, gateway_name):
    edge_gateways = vdc.list_edge_gateways()
    for gateway_dict in edge_gateways:
        if gateway_dict['name'] == gateway_name:
            return gateway_dict['href']
    return None


def _get_gateway(client: vcd_client.Client, org_name: str, ovdc_name: str,
                 network_name: str):
    # Check if routed org vdc network
    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(client)
    ovdc = vcd_utils.get_vdc(client, org_name=org_name, vdc_name=ovdc_name)
    try:
        routed_network_resource = ovdc.get_routed_orgvdc_network(network_name)
    except EntityNotFoundException:
        raise Exception(f'No routed network found named: {network_name} '
                        f'in ovdc {ovdc_name} and org {org_name}')
    routed_vdc_network = vdc_network.VdcNetwork(
        client=client,
        resource=routed_network_resource)
    network_id = utils.extract_id_from_href(routed_vdc_network.href)
    network_urn_id = f'{NETWORK_URN_PREFIX}:{network_id}'
    try:
        vdc_network_response = _get_vdc_network_response(
            cloudapi_client, network_urn_id)
    except Exception as err:
        LOGGER.error(f'Error when getting vdc network response when getting '
                     f'gateway: {str(err)}')
        return None
    gateway_name = vdc_network_response[VdcNetworkInfoKey.VALUES][0][
        VdcNetworkInfoKey.CONNECTION][VdcNetworkInfoKey.ROUTER_REF][
        VdcNetworkInfoKey.NAME]
    gateway_href = _get_gateway_href(ovdc, gateway_name)
    gateway = vcd_gateway.Gateway(client, name=gateway_name, href=gateway_href)
    return gateway


def _get_nsxt_backed_gateway_service(client: vcd_client.Client, org_name: str,
                                     ovdc_name: str, network_name: str):
    # Check if NSX-T backed gateway
    gateway: vcd_gateway.Gateway = _get_gateway(
        client=client,
        org_name=org_name,
        ovdc_name=ovdc_name,
        network_name=network_name)
    if not gateway:
        raise Exception(f'No gateway found for network: {network_name}')
    if not gateway.is_nsxt_backed():
        raise Exception('Gateway is not NSX-T backed for exposing cluster.')
    return NsxtBackedGatewayService(gateway, client)


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
        kubeconfig_with_exposed_ip: dict, internal_ip: str):
    """Construct script to update kubeconfig file with internal ip.

    :param dict kubeconfig_with_exposed_ip: the current kubeconfig
    :param str internal_ip: the internal ip of the control plane node

    :return: the script that will replace external ip in kubeconfig with
        internal ip

    :rtype: str
    """
    kubeconfig_with_internal_ip = re.sub(
        pattern=IP_PORT_REGEX,
        repl=f'{internal_ip}:6443',
        string=str(kubeconfig_with_exposed_ip)
    )

    script = f"#!/usr/bin/env bash\n" \
             f"echo \'{kubeconfig_with_internal_ip}\' > " \
             f"{CSE_CLUSTER_KUBECONFIG_PATH}\n"
    return script


def expose_cluster(client: vcd_client.Client, org_name: str, ovdc_name: str,
                   network_name: str, cluster_name: str, cluster_id: str,
                   internal_ip: str):
    """Create DNAT rule to expose a cluster.

    Get a free static IP from the edge gateway powering the Org VDC network,
        and create a DNAT rule to expose the @internal_ip

    :param vcd_client.Client client:
    :param str org_name:
    :param str ovdc_name:
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
        client, org_name, ovdc_name, network_name)
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
        raise Exception(f'Unable to add dnat rule with error: {str(err)}')
    return expose_ip


def handle_delete_expose_dnat_rule(client: vcd_client.Client,
                                   org_name: str,
                                   ovdc_name: str,
                                   network_name: str,
                                   cluster_name: str,
                                   cluster_id: str):
    """Delete DNAT rule that exposes a cluster.

    :param vcd_client.Client client:
    :param str org_name:
    :param str ovdc_name:
    :param str network_name:
    :param str cluster_name:
    :param str cluster_id:

    :returns: Nothing
    """
    nsxt_gateway_svc = _get_nsxt_backed_gateway_service(
        client, org_name, ovdc_name, network_name
    )
    expose_dnat_rule_name = construct_expose_dnat_rule_name(
        cluster_name, cluster_id
    )
    nsxt_gateway_svc.delete_dnat_rule(expose_dnat_rule_name)
