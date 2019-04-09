# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.nsxt.constants import ALL_NODES_IP_SET_NAME
from container_service_extension.nsxt.constants import \
    ALL_NODES_PODS_NSGROUP_NAME
from container_service_extension.nsxt.constants import ALL_PODS_IP_SET_NAME
from container_service_extension.nsxt.constants import \
    FIREWALL_EXCLUSION_IP_SET_NAME
from container_service_extension.nsxt.constants import \
    FIREWALL_EXCLUSION_NSGROUP_NAME
from container_service_extension.nsxt.constants import INSERT_POLICY
from container_service_extension.nsxt.constants import \
    NCP_BOUNDARY_FIREWALL_SECTION_NAME
from container_service_extension.nsxt.dfw_manager import DFWManager
from container_service_extension.nsxt.ipset_manager import IPSetManager
from container_service_extension.nsxt.nsgroup_manager import NSGroupManager


def setup_nsxt_constructs(nsxt_client,
                          nodes_ip_block_id,
                          pods_ip_block_id,
                          ncp_boundary_firewall_section_anchor_id,
                          firewall_excluded_ip_addesses=['30.0.0.0/24']):
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
    _create_ipset_for_firewall_exclusion(
        nsxt_client, firewall_excluded_ip_addesses)

    _create_all_nodes_pods_nsgroup(nsxt_client)
    _create_firewall_exclusion_nsgroup(nsxt_client)

    _create_ncp_boundary_firewall_section(
        nsxt_client, ncp_boundary_firewall_section_anchor_id)


def _create_ipset_for_node_pod_ip_blocks(nsxt_client,
                                         nodes_ip_block_ids,
                                         pods_ip_block_ids):
    ip_set_manager = IPSetManager(nsxt_client)

    all_nodes_ip_set = ip_set_manager.get_ip_set(name=ALL_NODES_IP_SET_NAME)
    if all_nodes_ip_set is None:
        nsxt_client.LOGGER.debug(f"Creating IPSet : {ALL_NODES_IP_SET_NAME}")
        all_nodes_ip_set = ip_set_manager.create_ip_set_from_ip_block(
            ALL_NODES_IP_SET_NAME,
            nodes_ip_block_ids)
    else:
        nsxt_client.LOGGER.debug(f"IPSet : {ALL_NODES_IP_SET_NAME} already "
                                 "exists.")

    all_pods_ip_set = ip_set_manager.get_ip_set(name=ALL_PODS_IP_SET_NAME)
    if all_pods_ip_set is None:
        nsxt_client.LOGGER.debug(f"Creating IPSet : {ALL_PODS_IP_SET_NAME}")
        all_pods_ip_set = ip_set_manager.create_ip_set_from_ip_block(
            ALL_PODS_IP_SET_NAME,
            pods_ip_block_ids)
    else:
        nsxt_client.LOGGER.debug(f"IPSet : {ALL_PODS_IP_SET_NAME} already "
                                 "exists.")


def _create_ipset_for_firewall_exclusion(nsxt_client,
                                         ip_addresses):
    ip_set_manager = IPSetManager(nsxt_client)

    firewall_exclusion_ip_set = ip_set_manager.get_ip_set(
        name=FIREWALL_EXCLUSION_IP_SET_NAME)
    if firewall_exclusion_ip_set is None:
        nsxt_client.LOGGER.debug(
            f"Creating IPSet : {FIREWALL_EXCLUSION_IP_SET_NAME}")
        firewall_exclusion_ip_set = ip_set_manager.create_ip_set(
            FIREWALL_EXCLUSION_IP_SET_NAME, ip_addresses)
    else:
        nsxt_client.LOGGER.debug(f"IPSet : {FIREWALL_EXCLUSION_IP_SET_NAME} "
                                 "already exists.")


def _create_all_nodes_pods_nsgroup(nsxt_client):
    nsgroup_manager = NSGroupManager(nsxt_client)
    ip_set_manager = IPSetManager(nsxt_client)

    nsgroup = nsgroup_manager.get_nsgroup(name=ALL_NODES_PODS_NSGROUP_NAME)
    if nsgroup is None:
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


def _create_firewall_exclusion_nsgroup(nsxt_client):
    nsgroup_manager = NSGroupManager(nsxt_client)
    ip_set_manager = IPSetManager(nsxt_client)

    nsgroup = nsgroup_manager.get_nsgroup(name=FIREWALL_EXCLUSION_NSGROUP_NAME)
    if nsgroup is None:
        firewall_exclusion_ip_set = ip_set_manager.get_ip_set(
            name=FIREWALL_EXCLUSION_IP_SET_NAME)['id']
        nsxt_client.LOGGER.debug(f"Creating NSGroup : "
                                 f"{FIREWALL_EXCLUSION_NSGROUP_NAME}")
        nsgroup = nsgroup_manager.create_nsgroup_from_ipsets(
            name=FIREWALL_EXCLUSION_NSGROUP_NAME,
            ipset_ids=[firewall_exclusion_ip_set])
    else:
        nsxt_client.LOGGER.debug(
            f"NSGroup : {FIREWALL_EXCLUSION_NSGROUP_NAME} already exists.")


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

        nsxt_client.LOGGER.debug(
            f"Creating DFW section : {NCP_BOUNDARY_FIREWALL_SECTION_NAME}")
        section = dfw_manager.create_firewall_section(
            name=NCP_BOUNDARY_FIREWALL_SECTION_NAME,
            tags=tags,
            anchor_id=ncp_boundary_firewall_section_anchor_id,
            insert_policy=INSERT_POLICY.INSERT_BEFORE)
    else:
        nsxt_client.LOGGER.debug("DFW section : "
                                 f"{NCP_BOUNDARY_FIREWALL_SECTION_NAME}"
                                 " already exists.")

    return section
