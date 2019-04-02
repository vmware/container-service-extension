# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from constants import ALL_NODES_IP_SET_NAME
from constants import ALL_NODES_PODS_NSGROUP_NAME
from constants import ALL_PODS_IP_SET_NAME
from constants import INSERT_POLICY
from constants import NCP_BOUNDARY_FIREWALL_SECTION_NAME
from dfw_manager import DFWManager
from ipset_manager import IPSetManager
from nsgroup_manager import NSGroupManager

from container_service_extension.logger import SERVER_NSXT_LOGGER as Logger


def setup_nsxt_constructs(nsxt_client,
                          nodes_ip_block_id,
                          pods_ip_block_id,
                          ncp_boundary_firewall_section_anchor_id):
    _create_ipset_for_node_pod_ip_blocks(nsxt_client,
                                         nodes_ip_block_id,
                                         pods_ip_block_id)
    _create_all_nodes_pods_nsgroup(nsxt_client)
    _create_ncp_boundary_firewall_section(
        nsxt_client, ncp_boundary_firewall_section_anchor_id)


def _create_ipset_for_node_pod_ip_blocks(nsxt_client,
                                         nodes_ip_block_ids,
                                         pods_ip_block_ids):
    ip_set_manager = IPSetManager(nsxt_client)

    all_nodes_ip_set = ip_set_manager.get_ip_set(name=ALL_NODES_IP_SET_NAME)
    if all_nodes_ip_set is None:
        Logger.debug(f"Creating IPSet : {ALL_NODES_IP_SET_NAME}")
        all_nodes_ip_set = ip_set_manager.create_ip_set_from_ip_block(
            ALL_NODES_IP_SET_NAME,
            nodes_ip_block_ids)
    else:
        Logger.debug(f"IPSet : {ALL_NODES_IP_SET_NAME} already exists.")

    all_pods_ip_set = ip_set_manager.get_ip_set(name=ALL_PODS_IP_SET_NAME)
    if all_pods_ip_set is None:
        Logger.debug(f"Creating IPSet : {ALL_PODS_IP_SET_NAME}")
        all_pods_ip_set = ip_set_manager.create_ip_set_from_ip_block(
            ALL_PODS_IP_SET_NAME,
            pods_ip_block_ids)
    else:
        Logger.debug(f"IPSet : {ALL_PODS_IP_SET_NAME} already exists.")


def _create_all_nodes_pods_nsgroup(nsxt_client):
    nsgroup_manager = NSGroupManager(nsxt_client)
    ip_set_manager = IPSetManager(nsxt_client)

    nsgroup = nsgroup_manager.get_nsgroup(name=ALL_NODES_PODS_NSGROUP_NAME)
    if nsgroup is None:
        all_nodes_ip_set_id = ip_set_manager.get_ip_set(
            name=ALL_NODES_IP_SET_NAME)['id']
        all_pods_ip_set_id = ip_set_manager.get_ip_set(
            name=ALL_PODS_IP_SET_NAME)['id']
        Logger.debug(f"Creating NSGroup : {ALL_NODES_PODS_NSGROUP_NAME}")
        nsgroup = nsgroup_manager.create_nsgroup_from_ipsets(
            name=ALL_NODES_PODS_NSGROUP_NAME,
            ipset_ids=[all_nodes_ip_set_id, all_pods_ip_set_id])
    else:
        Logger.debug(
            f"NSGroup : {ALL_NODES_PODS_NSGROUP_NAME} already exists.")


def _create_ncp_boundary_firewall_section(
        nsxt_client,
        ncp_boundary_firewall_section_anchor_id):
    dfw_manager = DFWManager(nsxt_client)

    section = dfw_manager.get_firewall_section(
        name=NCP_BOUNDARY_FIREWALL_SECTION_NAME)
    if section is None:
        tag = {}
        tag['scope'] = "ncp/fw_sect_marker"
        tag['tag'] = "top"
        tags = [tag]

        Logger.debug(
            f"Creating DFW section : {NCP_BOUNDARY_FIREWALL_SECTION_NAME}")
        section = dfw_manager.create_firewall_section(
            name=NCP_BOUNDARY_FIREWALL_SECTION_NAME,
            tags=tags,
            anchor_id=ncp_boundary_firewall_section_anchor_id,
            insert_policy=INSERT_POLICY.INSERT_BEFORE)
    else:
        Logger.debug(f"DFW section : {NCP_BOUNDARY_FIREWALL_SECTION_NAME}"
                     " already exists.")

    return section
