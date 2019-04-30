# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.nsxt.constants import \
    ALL_NODES_PODS_NSGROUP_NAME
from container_service_extension.nsxt.constants import FIREWALL_ACTION
from container_service_extension.nsxt.constants import INSERT_POLICY
from container_service_extension.nsxt.constants import \
    NCP_BOUNDARY_BOTTOM_FIREWALL_SECTION_NAME
from container_service_extension.nsxt.dfw_manager import DFWManager
from container_service_extension.nsxt.nsgroup_manager import NSGroupManager


class ClusterNetworkIsolater(object):
    """Facilitate network isolation of PKS clusters."""

    def __init__(self, nsxt_client):
        """Initialize a ClusterNetworkIsolater object.

        :param NSXTCLient nsxt_client: client to make NSX-T REST requests.
        """
        self._nsxt_client = nsxt_client

    def isolate_cluster(self, cluster_name, cluster_id):
        """Isolate a PKS cluster's network.

        :param str cluster_name: name of the cluster whose network needs
            isolation.
        :param str cluster_id: id of the cluster whose network needs isolation.
            Cluster id is used to identify the tagged logical switch and ports
            powering the T1 routers of the cluster.
        """
        n_id, p_id, np_id = self._create_nsgroups_for_cluster(
            cluster_name, cluster_id)

        sec_id = self._create_firewall_section_for_cluster(
            cluster_name, np_id).get('id')

        nsgroup_manager = NSGroupManager(self._nsxt_client)
        anp_id = \
            nsgroup_manager.get_nsgroup(ALL_NODES_PODS_NSGROUP_NAME).get('id')

        self._create_firewall_rules_for_cluster(
            sec_id, n_id, p_id, np_id, anp_id)

    def remove_cluster_isolation(self, cluster_name):
        """Revert isolatation of a PKS cluster's network.

        :param str cluster_name: name of the cluster whose network isolation
            needs to be reverted.
        """
        firewall_section_name = \
            self._get_firewall_section_name_for_cluster(cluster_name)

        nodes_nsgroup_name = self._get_nodes_nsgroup_name(cluster_name)
        pods_nsgroup_name = self._get_pods_nsgroup_name(cluster_name)
        nodes_pods_nsgroup_name = \
            self._get_nodes_pods_nsgroup_name(cluster_name)

        dfw_manager = DFWManager(self._nsxt_client)
        nsgroup_manager = NSGroupManager(self._nsxt_client)

        dfw_manager.delete_firewall_section(firewall_section_name,
                                            cascade=True)
        nsgroup_manager.delete_nsgroup(nodes_pods_nsgroup_name, force=True)
        nsgroup_manager.delete_nsgroup(nodes_nsgroup_name, force=True)
        nsgroup_manager.delete_nsgroup(pods_nsgroup_name, force=True)

    def _create_nsgroups_for_cluster(self, cluster_name, cluster_id):
        """Create NSgroups for cluster isolateion.

        One NSGroup to include all nodes in the cluster.
        One NSGroup to include all pods in the cluster.
        One NSgroup to include all nodes and pods in the cluster.

        :param str cluster_name: name of the cluster whose network is being
            isolated.
        :param str cluster_id: id of the cluster whose network is being
            isolated.
        """
        nodes_nsgroup = self._create_nsgroup_for_cluster_nodes(
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

    def _create_nsgroup_for_cluster_nodes(self, cluster_name, cluster_id):
        """Create NSGroup for all nodes in the cluster.

        If NSGroup already exists, delete it and re-create it. Since this group
        is based on cluster name, it possible that a previously deployed
        cluster on deletion failed to cleanup it's NSGroups, we shouldn't
        re-use that group rather create it afresh with the proper cluster
        id tag based membership criteria.

        :param str cluster_name: name of the cluster whose network is being
            isolated.
        :param str cluster_id: id of the cluster whose network is being
            isolated.

        :return: NSGroup containing all the nodes in the cluster, as a JSON
            dictionary.

        :rtype: dict
        """
        name = self._get_nodes_nsgroup_name(cluster_name)
        nsgroup_manager = NSGroupManager(self._nsxt_client)
        nodes_nsgroup = nsgroup_manager.get_nsgroup(name)
        if nodes_nsgroup:
            self._nsxt_client.LOGGER.debug(f"NSGroup : {name} already exists.")
            nsgroup_manager.delete_nsgroup(name, force=True)
            self._nsxt_client.LOGGER.debug(f"Deleted NSGroup : {name}.")

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

        self._nsxt_client.LOGGER.debug(f"Creating NSGroup : {name}.")
        nodes_nsgroup = nsgroup_manager.create_nsgroup(
            name, membership_criteria=[criteria])

        return nodes_nsgroup

    def _create_nsgroup_for_cluster_pods(self, cluster_name, cluster_id):
        """Create NSGroup for all pods in a cluster.

        If NSGroup already exists, delete it and re-create it. Since this group
        is based on cluster name, it possible that a previously deployed
        cluster on deletion failed to cleanup it's NSGroups, we shouldn't
        re-use that group rather create it afresh with the proper cluster
        id tag based membership criteria.

        :param str cluster_name: name of the cluster whose network is being
            isolated.
        :param str cluster_id: id of the cluster whose network is being
            isolated.

        :return: NSGroup containing all the pods in the cluster, as a JSON
            dictionary.

        :rtype: dict
        """
        name = self._get_pods_nsgroup_name(cluster_name)
        nsgroup_manager = NSGroupManager(self._nsxt_client)
        pods_nsgroup = nsgroup_manager.get_nsgroup(name)
        if pods_nsgroup:
            self._nsxt_client.LOGGER.debug(f"NSGroup : {name} already exists.")
            nsgroup_manager.delete_nsgroup(name, force=True)
            self._nsxt_client.LOGGER.debug(f"Deleted NSGroup : {name}.")

        criteria = {}
        criteria['resource_type'] = "NSGroupTagExpression"
        criteria['target_type'] = "LogicalPort"
        criteria['scope'] = "ncp/cluster"
        criteria['tag'] = f"pks-{cluster_id}"

        self._nsxt_client.LOGGER.debug(f"Creating NSGroup : {name}.")
        pods_nsgroup = nsgroup_manager.create_nsgroup(
            name, membership_criteria=[criteria])

        return pods_nsgroup

    def _create_nsgroup_for_cluster_nodes_and_pods(self,
                                                   cluster_name,
                                                   nodes_nsgroup_id,
                                                   pods_nsgroup_id):
        """Create NSGroup for all nodes and pods in a cluster.

        If NSGroup already exists, delete it and re-create it. Since this group
        is based on cluster name, it possible that a previously deployed
        cluster on deletion failed to cleanup it's NSGroups, we shouldn't
        re-use that group rather create it afresh with the proper member
        NSGroups ids.

        :param str cluster_name: name of the cluster whose network is being
            isolated.
        :param str nodes_nsgroup_id:
        :param str pods_nsgroup_id:

        :return: NSGroup containing all the nodes and pods in the cluster, as a
            JSON dictionary.

        :rtype: dict
        """
        name = self._get_nodes_pods_nsgroup_name(cluster_name)
        nsgroup_manager = NSGroupManager(self._nsxt_client)
        nodes_pods_nsgroup = nsgroup_manager.get_nsgroup(name)
        if nodes_pods_nsgroup:
            self._nsxt_client.LOGGER.debug(f"NSGroup : {name} already exists.")
            nsgroup_manager.delete_nsgroup(name, force=True)
            self._nsxt_client.LOGGER.debug(f"Deleted NSGroup : {name}.")

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

        self._nsxt_client.LOGGER.debug(f"Creating NSGroup : {name}.")
        nodes_pods_nsgroup = nsgroup_manager.create_nsgroup(
            name, members=members)

        return nodes_pods_nsgroup

    def _get_firewall_section_name_for_cluster(self, cluster_name):
        return f"isolate_{cluster_name}"

    def _create_firewall_section_for_cluster(self,
                                             cluster_name,
                                             applied_to_nsgroup_id):
        """Create DFW Section for the cluster.

        If DFW Section already exists, delete it and re-create it. Since this
        section is based on cluster name, it possible that a previously
        deployed cluster on deletion failed to cleanup properly. We shouldn't
        re-use such a section rather create it afresh with new rules pointing
        to the correct NSGroups.

        :param str cluster_name: name of the cluster whose network is being
            isolated.
        :param str applied_to_nsgroup_id: id of the NSGroup on which the rules
            in this DFW SEction will apply to.
        """
        section_name = self._get_firewall_section_name_for_cluster(
            cluster_name)
        dfw_manager = DFWManager(self._nsxt_client)
        section = dfw_manager.get_firewall_section(section_name)
        if section:
            self._nsxt_client.LOGGER.debug(f"DFW section : {section_name} "
                                           "already exists.")
            dfw_manager.delete_firewall_section(section_name, cascade=True)
            self._nsxt_client.LOGGER.debug("Deleted DFW section : "
                                           f"{section_name} ")

        target = {}
        target['target_type'] = "NSGroup"
        target['target_id'] = applied_to_nsgroup_id

        anchor_section = dfw_manager.get_firewall_section(
            NCP_BOUNDARY_BOTTOM_FIREWALL_SECTION_NAME)

        self._nsxt_client.LOGGER.debug("Creating DFW section : "
                                       f"{section_name}")
        section = dfw_manager.create_firewall_section(
            name=section_name,
            applied_tos=[target],
            anchor_id=anchor_section['id'],
            insert_policy=INSERT_POLICY.INSERT_AFTER)

        return section

    def _create_firewall_rules_for_cluster(self,
                                           section_id,
                                           nodes_nsgroup_id,
                                           pods_nsgroup_id,
                                           nodes_pods_nsgroup_id,
                                           all_nodes_pods_nsgroup_id):
        """Create DFW Rules to isolate a cluster network.

        One rule to limit communication from pods to nodes.
        One rule to allow other form of communication between nodes and pods.
        One rule to isolate the nodes and pods of this cluster from other
            clusters.

        :param str section_id: id of the DFW Section where these rules will be
            added.
        :param str nodes_nsgroup_id:
        :param str pods_nsgroup_id:
        :param str nodes_pods_nsgroup_id:
        :param str all_nodes_pods_nsgroup_id:
        """
        dfw_manager = DFWManager(self._nsxt_client)
        # rule1_name = "Block pods to node communication"
        # self._nsxt_client.LOGGER.debug(f"Creating DFW rule : {rule1_name}")
        # rule1 = dfw_manager.create_dfw_rule(
        #    section_id=section_id,
        #    rule_name=rule1_name,
        #    source_nsgroup_id=pods_nsgroup_id,
        #    dest_nsgroup_id=nodes_nsgroup_id,
        #    action=FIREWALL_ACTION.DROP)

        rule2_name = "Allow cluster node-pod to cluster node-pod communication"
        self._nsxt_client.LOGGER.debug(f"Creating DFW rule : {rule2_name}")
        rule2 = dfw_manager.create_dfw_rule(
            section_id=section_id,
            rule_name=rule2_name,
            source_nsgroup_id=nodes_pods_nsgroup_id,
            dest_nsgroup_id=nodes_pods_nsgroup_id,
            action=FIREWALL_ACTION.ALLOW,
            # anchor_rule_id=rule1['id'],
            # insert_policy=INSERT_POLICY.INSERT_AFTER
        )

        rule3_name = "Block cluster node-pod to all-node-pod communication"
        self._nsxt_client.LOGGER.debug(f"Creating DFW rule : {rule3_name}")
        dfw_manager.create_dfw_rule(
            section_id=section_id,
            rule_name=rule3_name,
            source_nsgroup_id=nodes_pods_nsgroup_id,
            dest_nsgroup_id=all_nodes_pods_nsgroup_id,
            action=FIREWALL_ACTION.DROP,
            anchor_rule_id=rule2['id'],
            insert_policy=INSERT_POLICY.INSERT_AFTER)
