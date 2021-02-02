# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.lib.nsxt.constants import ALL_NODES_IP_SET_NAME  # noqa: E501
from container_service_extension.lib.nsxt.constants import \
    ALL_NODES_PODS_NSGROUP_NAME
from container_service_extension.lib.nsxt.constants import ALL_PODS_IP_SET_NAME
from container_service_extension.lib.nsxt.constants import INSERT_POLICY
from container_service_extension.lib.nsxt.constants import \
    NCP_BOUNDARY_BOTTOM_FIREWALL_SECTION_NAME
from container_service_extension.lib.nsxt.constants import \
    NCP_BOUNDARY_FIREWALL_SECTION_NAME
from container_service_extension.lib.nsxt.constants import \
    NCP_BOUNDARY_TOP_FIREWALL_SECTION_NAME
from container_service_extension.lib.nsxt.dfw_manager import DFWManager
from container_service_extension.lib.nsxt.ipset_manager import IPSetManager
from container_service_extension.lib.nsxt.nsgroup_manager import NSGroupManager


def setup_nsxt_constructs(nsxt_client,
                          nodes_ip_block_id,
                          pods_ip_block_id,
                          ncp_boundary_firewall_section_anchor_id):
    """Set up one time NSX-T construct which will aid in network isolation.

    :param list nodes_ip_block_id: list of strings, where each entry represents
        id of a non routable ip block from which ip of cluster nodes will be
        assigned.
    :param list pods_ip_block_id: list of strings, where each entry represents
        id of a non routable ip block from which ip of cluster pods will be
        assigned.
    :param str ncp_boundary_firewall_section_anchor_id: id of the firewal
        section which will act as anchor for the NCP fw_sector/top firewall
        section.
    """
    _create_ipset_for_node_pod_ip_blocks(nsxt_client,
                                         nodes_ip_block_id,
                                         pods_ip_block_id)

    _create_all_nodes_pods_nsgroup(nsxt_client)

    dfw_manager = DFWManager(nsxt_client)
    dfw_manager.delete_firewall_section(
        name=NCP_BOUNDARY_FIREWALL_SECTION_NAME)
    _create_ncp_boundary_firewall_section(
        nsxt_client, ncp_boundary_firewall_section_anchor_id,
        NCP_BOUNDARY_TOP_FIREWALL_SECTION_NAME, "top")
    _create_ncp_boundary_firewall_section(
        nsxt_client, ncp_boundary_firewall_section_anchor_id,
        NCP_BOUNDARY_BOTTOM_FIREWALL_SECTION_NAME, "bottom")


def _create_ipset_for_node_pod_ip_blocks(nsxt_client,
                                         nodes_ip_block_ids,
                                         pods_ip_block_ids):
    ip_set_manager = IPSetManager(nsxt_client)

    all_nodes_ip_set = ip_set_manager.get_ip_set(name=ALL_NODES_IP_SET_NAME)
    if not all_nodes_ip_set:
        nsxt_client.LOGGER.debug(f"Creating IPSet : {ALL_NODES_IP_SET_NAME}")
        all_nodes_ip_set = ip_set_manager.create_ip_set_from_ip_block(
            ALL_NODES_IP_SET_NAME,
            nodes_ip_block_ids)
    else:
        nsxt_client.LOGGER.debug(f"IPSet : {ALL_NODES_IP_SET_NAME} already "
                                 "exists.")

    all_pods_ip_set = ip_set_manager.get_ip_set(name=ALL_PODS_IP_SET_NAME)
    if not all_pods_ip_set:
        nsxt_client.LOGGER.debug(f"Creating IPSet : {ALL_PODS_IP_SET_NAME}")
        all_pods_ip_set = ip_set_manager.create_ip_set_from_ip_block(
            ALL_PODS_IP_SET_NAME,
            pods_ip_block_ids)
    else:
        nsxt_client.LOGGER.debug(f"IPSet : {ALL_PODS_IP_SET_NAME} already "
                                 "exists.")


def _create_all_nodes_pods_nsgroup(nsxt_client):
    nsgroup_manager = NSGroupManager(nsxt_client)
    ip_set_manager = IPSetManager(nsxt_client)

    nsgroup = nsgroup_manager.get_nsgroup(name=ALL_NODES_PODS_NSGROUP_NAME)
    if not nsgroup:
        all_nodes_ip_set_id = ip_set_manager.get_ip_set(
            name=ALL_NODES_IP_SET_NAME)['id']
        all_pods_ip_set_id = ip_set_manager.get_ip_set(
            name=ALL_PODS_IP_SET_NAME)['id']
        nsxt_client.LOGGER.debug(f"Creating NSGroup : "
                                 f"{ALL_NODES_PODS_NSGROUP_NAME}")
        nsgroup = nsgroup_manager.create_nsgroup_from_ipsets(
            name=ALL_NODES_PODS_NSGROUP_NAME,
            ipset_ids=[all_nodes_ip_set_id, all_pods_ip_set_id])
    else:
        nsxt_client.LOGGER.debug(
            f"NSGroup : {ALL_NODES_PODS_NSGROUP_NAME} already exists.")


def _create_ncp_boundary_firewall_section(
        nsxt_client,
        anchor_id,
        firewall_section_name,
        tag_value):
    dfw_manager = DFWManager(nsxt_client)

    section = dfw_manager.get_firewall_section(name=firewall_section_name)
    if not section:
        tag = {}
        tag['scope'] = "ncp/fw_sect_marker"
        tag['tag'] = tag_value
        tags = [tag]

        nsxt_client.LOGGER.debug(
            f"Creating DFW section : {firewall_section_name}")
        section = dfw_manager.create_firewall_section(
            name=firewall_section_name,
            tags=tags,
            anchor_id=anchor_id,
            insert_policy=INSERT_POLICY.INSERT_BEFORE)
    else:
        nsxt_client.LOGGER.debug(f"DFW section : {firewall_section_name} "
                                 "already exists.")

    return section
