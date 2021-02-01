# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from requests.exceptions import HTTPError

from container_service_extension.lib.nsxt.constants import RequestMethodVerb


class NSGroupManager(object):
    """Facilitate Create, Retrieve, Delete operations on NSGroups."""

    def __init__(self, nsxt_client):
        """Initialize a NSXGroupMnaager object.

        :param NSXTCLient nsxt_client: client to make NSX-T REST requests.
        """
        self._nsxt_client = nsxt_client

    def list_nsgroups(self):
        """List all NSGroups.

        :return: All NSGroups in the system as a list of dictionaries, where
            each dictionary represent a NSGroup.

        :rtype: list
        """
        resource_url_fragment = "ns-groups"
        response = self._nsxt_client.do_request(
            method=RequestMethodVerb.GET,
            resource_url_fragment=resource_url_fragment)

        nsgroups = response['results']
        return nsgroups

    def get_nsgroup(self, name=None, id=None):
        """Get information of a NSGroup identified by id or name.

        Identification by id takes precedence. Will return None if no matching
        NSGroup is found.

        :param str name: name of the NSGroup whose details are to be retrieved.
        :param str id: id of the NSGroup whose details are to be retrieved.

        :return: details of the NSGroup as a dictionary.

        :rtype: dict

        :raises HTTPError: If the underlying REST call fails with any status
            code other than 404.
        """
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
                if err.response.status_code != 404:
                    raise
                else:
                    return

        nsgroups = self.list_nsgroups()
        for nsgroup in nsgroups:
            if nsgroup['display_name'].lower() == name.lower():
                return nsgroup

    def create_nsgroup(self, name, members=None, membership_criteria=None):
        """Create a new NSGroup.

        :param str name: name of the NSGroup to be created.
        :param list members: list of dictionaries. Where each dictionary
            represents a direct member of the NSGroup, generally expressed as
            NSGroupSimpleExpression JSON object.
        :param dict membership_criteria: dictionary representing indirect
            (evaluated) members of the NSGroup. Generally expressed as a
            NSGroupComplexExpression, NSGroupTagExpression or
            NSGroupSimpleExpression JSON object.

        :return: details of the newly created NSGroup as a dictionary.

        :rtype: dict
        """
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
        """Create a new NSGroup from a list of IPSets.

        :param str name: name of the NSGroup to be created.
        :param list ip_sets: list of ids (str) of IPSets, which are direct
            members of the NSGroup.

        :return: details of the newly created NSGroup as a dictionary.

        :rtype: dict
        """
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
        """Delete a NSGroup identified by id or name.

        Identification by id takes precedence. Will return False if no matching
        NSGroup is found.

        :param str name: name of the NSGroup to be deleted..
        :param str id: id of the NSGroup to be deleted.
        :param bool force: if True, a force deletion will be attempted.

        :return: True, if the delete operation is successful, else False.

        :rtype: bool
        """
        if not name and not id:
            return False

        if not id:
            nsgroup = self.get_nsgroup(name)
            if nsgroup:
                id = nsgroup['id']
            else:
                self._nsxt_client.LOGGER.debug(f"NSGroup : {name} not found. "
                                               "Unable to delete.")
                return False
        resource_url_fragment = f"ns-groups/{id}"
        if force:
            resource_url_fragment += "?force=true"

        self._nsxt_client.do_request(
            method=RequestMethodVerb.DELETE,
            resource_url_fragment=resource_url_fragment)
        return True
