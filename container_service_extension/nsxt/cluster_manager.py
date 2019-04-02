# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.logger import SERVER_NSXT_LOGGER as Logger
from container_service_extension.nsxt.constants import \
    ALL_NODES_PODS_NSGROUP_NAME
from container_service_extension.nsxt.constants import FIREWALL_ACTION
from container_service_extension.nsxt.constants import INSERT_POLICY
from container_service_extension.nsxt.constants import \
    NCP_BOUNDARY_FIREWALL_SECTION_NAME
from container_service_extension.nsxt.dfw_manager import DFWManager
from container_service_extension.nsxt.nsgroup_manager import NSGroupManager


class ClusterManager(object):
    """."""

    def __init__(self, nsxt_client):
        self._nsxt_client = nsxt_client

    def isolate_cluster(self, cluster_name, cluster_id,):
        n_id, p_id, np_id = self._create_nsgroups_for_cluster(
            cluster_name, cluster_id)

        sec_id = self._create_firewall_section_for_cluster(
            cluster_name, np_id)['id']

        nsgroup_manager = NSGroupManager(self._nsxt_client)
        anp_id = nsgroup_manager.get_nsgroup(ALL_NODES_PODS_NSGROUP_NAME)['id']

        self._create_firewall_rules_for_cluster(
            sec_id, n_id, p_id, np_id, anp_id)

    def cleanup_cluster(self, cluster_name):
        filewall_section_name = \
            self._get_firewall_section_name_for_cluster(cluster_name)

        nodes_nsgroup_name = self._get_nodes_nsgroup_name(cluster_name)
        pods_nsgroup_name = self._get_pods_nsgroup_name(cluster_name)
        nodes_pods_nsgroup_name = \
            self._get_nodes_pods_nsgroup_name(cluster_name)

        dfw_manager = DFWManager(self._nsxt_client)
        nsgroup_manager = NSGroupManager(self._nsxt_client)

        dfw_manager.delete_firewall_section(filewall_section_name,
                                            cascade=True)
        nsgroup_manager.delete_nsgroup(nodes_pods_nsgroup_name, force=True)
        nsgroup_manager.delete_nsgroup(nodes_nsgroup_name, force=True)
        nsgroup_manager.delete_nsgroup(pods_nsgroup_name, force=True)

    def _create_nsgroups_for_cluster(self, cluster_name, cluster_id):
        nodes_nsgroup = self._create_cluster_nodes_nsgroup(
            cluster_name, cluster_id)
        nodes_nsgroup_id = nodes_nsgroup['id']

        pods_nsgroup = self._create_nsgroup_for_cluster_pods(
            cluster_name, cluster_id)
        pods_nsgroup_id = pods_nsgroup['id']

        nodes_pods_nsgroup = self._create_nsgroup_for_cluster_nodes_and_pods(
            cluster_name, nodes_nsgroup_id, pods_nsgroup_id)
        nodes_pods_nsgroup_id = nodes_pods_nsgroup['id']

        return (nodes_nsgroup_id, pods_nsgroup_id, nodes_pods_nsgroup_id)

    def _get_nodes_nsgroup_name(self, cluster_name):
        return f"{cluster_name}_nodes"

    def _get_pods_nsgroup_name(self, cluster_name):
        return f"{cluster_name}_pods"

    def _get_nodes_pods_nsgroup_name(self, cluster_name):
        return f"{cluster_name}_nodes_pods"

    def _create_cluster_nodes_nsgroup(self, cluster_name, cluster_id):
        name = self._get_nodes_nsgroup_name(cluster_name)
        nsgroup_manager = NSGroupManager(self._nsxt_client)
        nodes_nsgroup = nsgroup_manager.get_nsgroup(name)
        if nodes_nsgroup is None:
            criteria = {}
            criteria['resource_type'] = "NSGroupComplexExpression"

            expression1 = {}
            expression1['resource_type'] = "NSGroupTagExpression"
            expression1['target_type'] = "LogicalSwitch"
            expression1['scope'] = "pks/cluster"
            expression1['tag'] = str(cluster_id)

            expression2 = {}
            expression2['resource_type'] = "NSGroupTagExpression"
            expression2['target_type'] = "LogicalSwitch"
            expression2['scope'] = "pks/floating_ip"

            criteria['expressions'] = [expression1, expression2]

            Logger.debug(f"Creating NSGroup : {name}.")
            nodes_nsgroup = nsgroup_manager.create_nsgroup(
                name, membership_criteria=[criteria])
        else:
            Logger.debug(f"NSGroup : {name} already exists.")

        return nodes_nsgroup

    def _create_nsgroup_for_cluster_pods(self, cluster_name, cluster_id):
        name = self._get_pods_nsgroup_name(cluster_name)
        nsgroup_manager = NSGroupManager(self._nsxt_client)
        pods_nsgroup = nsgroup_manager.get_nsgroup(name)
        if pods_nsgroup is None:
            criteria = {}
            criteria['resource_type'] = "NSGroupTagExpression"
            criteria['target_type'] = "LogicalPort"
            criteria['scope'] = "ncp/cluster"
            criteria['tag'] = str(cluster_id)

            Logger.debug(f"Creating NSGroup : {name}.")
            pods_nsgroup = nsgroup_manager.create_nsgroup(
                name, membership_criteria=[criteria])
        else:
            Logger.debug(f"NSGroup : {name} already exists.")

        return pods_nsgroup

    def _create_nsgroup_for_cluster_nodes_and_pods(self,
                                                   cluster_name,
                                                   nodes_nsgroup_id,
                                                   pods_nsgroup_id):
        name = self._get_nodes_pods_nsgroup_name(cluster_name)
        nsgroup_manager = NSGroupManager(self._nsxt_client)
        nodes_pods_nsgroup = nsgroup_manager.get_nsgroup(name)
        if nodes_pods_nsgroup is None:
            member1 = {}
            member1['resource_type'] = "NSGroupSimpleExpression"
            member1['target_type'] = "NSGroup"
            member1['target_property'] = "id"
            member1['op'] = "EQUALS"
            member1['value'] = nodes_nsgroup_id

            member2 = {}
            member2['resource_type'] = "NSGroupSimpleExpression"
            member2['target_type'] = "NSGroup"
            member2['target_property'] = "id"
            member2['op'] = "EQUALS"
            member2['value'] = pods_nsgroup_id

            members = [member1, member2]

            Logger.debug(f"Creating NSGroup : {name}.")
            nodes_pods_nsgroup = nsgroup_manager.create_nsgroup(
                name, members=members)
        else:
            Logger.debug(f"NSGroup : {name} already exists.")

        return nodes_pods_nsgroup

    def _get_firewall_section_name_for_cluster(self, cluster_name):
        return f"isolate_{cluster_name}"

    def _create_firewall_section_for_cluster(self,
                                             cluster_name,
                                             applied_to_nsgroup_id):
        section_name = self._get_firewall_section_name_for_cluster(
            cluster_name)
        dwf_manager = DFWManager(self._nsxt_client)
        section = dwf_manager.get_firewall_section(section_name)
        if section is None:
            target = {}
            target['target_type'] = "NSGroup"
            target['target_id'] = applied_to_nsgroup_id

            anchor_section = dwf_manager.get_firewall_section(
                NCP_BOUNDARY_FIREWALL_SECTION_NAME)

            Logger.debug(f"Creating DFW section : {section_name}")
            section = dwf_manager.create_firewall_section(
                name=section_name,
                applied_tos=[target],
                anchor_id=anchor_section['id'],
                insert_policy=INSERT_POLICY.INSERT_AFTER)
        else:
            Logger.debug(f"DFW section : {section_name} already exists.")

        return section

    def _create_firewall_rules_for_cluster(self,
                                           section_id,
                                           nodes_nsgroup_id,
                                           pods_nsgroup_id,
                                           nodes_pods_nsgroup_id,
                                           all_nodes_pods_nsgroup_id):
        dfw_manager = DFWManager(self._nsxt_client)
        rule1_name = "Block pods to node communication"
        Logger.debug(f"Creating DFW rule : {rule1_name}")
        rule1 = dfw_manager.create_dfw_rule(
            section_id=section_id,
            rule_name=rule1_name,
            source_nsgroup_id=pods_nsgroup_id,
            dest_nsgroup_id=nodes_nsgroup_id,
            action=FIREWALL_ACTION.DROP)

        rule2_name = "Allow cluster node-pod to cluster node-pod communication"
        Logger.debug(f"Creating DFW rule : {rule2_name}")
        rule2 = dfw_manager.create_dfw_rule(
            section_id=section_id,
            rule_name=rule2_name,
            source_nsgroup_id=nodes_pods_nsgroup_id,
            dest_nsgroup_id=nodes_pods_nsgroup_id,
            action=FIREWALL_ACTION.ALLOW,
            anchor_rule_id=rule1['id'],
            insert_policy=INSERT_POLICY.INSERT_AFTER)

        rule3_name = "Block cluster node-pod to all-node-pod communication"
        Logger.debug(f"Creating DFW rule : {rule3_name}")
        dfw_manager.create_dfw_rule(
            section_id=section_id,
            rule_name=rule3_name,
            source_nsgroup_id=nodes_pods_nsgroup_id,
            dest_nsgroup_id=all_nodes_pods_nsgroup_id,
            action=FIREWALL_ACTION.DROP,
            anchor_rule_id=rule2['id'],
            insert_policy=INSERT_POLICY.INSERT_AFTER)
