# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from constants import RequestMethodVerb


class NSGroupManager(object):
    """."""

    def __init__(self, nsxt_client):
        self._nsxt_client = nsxt_client

    def list_nsgroups(self):
        resource_url_fragment = "ns-groups"
        response = self._nsxt_client.do_request(
            method=RequestMethodVerb.GET,
            resource_url_fragment=resource_url_fragment)

        nsgroups = response['results']
        return nsgroups

    def get_nsgroup(self, name=None, id=None):
        if id is None and name is None:
            return None

        nsgroups = self.list_nsgroups()
        for nsgroup in nsgroups:
            if id is not None and nsgroup['id'] == id:
                return nsgroup
            elif name is not None and nsgroup['display_name'] == name:
                return nsgroup

        return None

    def create_nsgroup(self, name, members=None, membership_criteria=None):
        resource_url_fragment = "ns-groups"

        data = {}
        data['display_name'] = name
        if members is not None:
            data['members'] = members
        if membership_criteria is not None:
            data['membership_criteria'] = membership_criteria

        nodes_nsgroup = self._nsxt_client.do_request(
            method=RequestMethodVerb.POST,
            resource_url_fragment=resource_url_fragment,
            payload=data)

        return nodes_nsgroup

    def create_nsgroup_from_ipsets(self, name, ipset_ids):
        members = []
        for ipset_id in ipset_ids:
            member = {}
            member['resource_type'] = "NSGroupSimpleExpression"
            member['target_type'] = "IPSet"
            member['target_property'] = "id"
            member['op'] = "EQUALS"
            member['value'] = ipset_id

            members.append(member)

        return self.create_nsgroup(name, members=members)
