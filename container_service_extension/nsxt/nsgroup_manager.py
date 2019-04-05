# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from requests.exceptions import HTTPError

from container_service_extension.logger import SERVER_NSXT_LOGGER as LOGGER
from container_service_extension.nsxt.constants import RequestMethodVerb


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
        if not id and not name:
            return

        if id:
            resource_url_fragment = f"ns-groups/{id}"
            try:
                response = self._nsxt_client.do_request(
                    method=RequestMethodVerb.GET,
                    resource_url_fragment=resource_url_fragment)
                return response
            except HTTPError as err:
                if err.code != 404:
                    raise

        nsgroups = self.list_nsgroups()
        for nsgroup in nsgroups:
            if nsgroup['display_name'].lower() == name.lower():
                return nsgroup

    def create_nsgroup(self, name, members=None, membership_criteria=None):
        resource_url_fragment = "ns-groups"

        data = {}
        data['display_name'] = name
        if members:
            data['members'] = members
        if membership_criteria:
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

    def delete_nsgroup(self, name=None, id=None, force=False):
        if not name and not id:
            return False

        if not id:
            nsgroup = self.get_nsgroup(name)
            if nsgroup:
                id = nsgroup['id']
            else:
                LOGGER.debug(f"NSGroup : {name} not found. Unable to delete.")
                return False
        resource_url_fragment = f"ns-groups/{id}"
        if force:
            resource_url_fragment += "?force=true"

        self._nsxt_client.do_request(
            method=RequestMethodVerb.DELETE,
            resource_url_fragment=resource_url_fragment)
        return True
