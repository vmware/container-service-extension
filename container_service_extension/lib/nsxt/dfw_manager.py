# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from requests.exceptions import HTTPError

from container_service_extension.lib.nsxt.constants import RequestMethodVerb


class DFWManager(object):
    """Facilitate Create, Retrieve, Delete operations on DFW.

    Works on Distributed Firewall Section and Rules.
    """

    def __init__(self, nsxt_client):
        """Initialize a DFWManager object.

        :param NSXTCLient nsxt_client: client to make NSX-T REST requests.
        """
        self._nsxt_client = nsxt_client

    def list_firewall_sections(self):
        """List all Distributed Firewall Sections.

        :return: All DFW sections in the system as a list of dictionaries,
            where each dictionary represent a DFW Section.

        :rtype: list
        """
        resource_url_fragment = "firewall/sections"

        response = self._nsxt_client.do_request(
            method=RequestMethodVerb.GET,
            resource_url_fragment=resource_url_fragment)

        firewall_sections = response['results']
        return firewall_sections

    def get_firewall_section(self, name=None, id=None):
        """Get information of a DFW Section identified by id or name.

        Identification by id takes precedence. Will return None if no matching
        DFW Section is found.

        :param str name: name of the DFW Section whose details are to be
            retrieved.
        :param str id: id of the DFW Section whose details are to be retrieved.

        :return: details of the DFW IPSet as a dictionary.

        :rtype: dict

        :raises HTTPError: If the underlying REST call fails with any status
            code other than 404.
        """
        if not name and not id:
            return

        if id:
            resource_url_fragment = f"firewall/sections/{id}"
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

        fw_sections = self.list_firewall_sections()
        for fw_section in fw_sections:
            if fw_section['display_name'].lower() == name.lower():
                return fw_section

        return

    def create_firewall_section(self,
                                name,
                                applied_tos=None,
                                tags=None,
                                anchor_id=None,
                                insert_policy=None):
        """Create a new DFW Section.

        :param str name: name of the DFW Section to be created.
        :param list applied_tos: list of dicr, where each dict represents an
            individual target, normally are NSGroup.
        :param list tags: list of dictionaries, where each dictionary contains
            scope and tag key-value pairs.
        :param str anchor_id: id of another DFW Section that will be used to
            figure out the position of the newly created DFW Section.
        :param constants.INSERT_POLICY insert_policy: the relative position of
            the newly created DFW Section to the anchor section.

        :return: details of the newly created DFW Section as a dictionary.

        :rtype: dict
        """
        resource_url_fragment = "firewall/sections"
        if anchor_id or insert_policy:
            resource_url_fragment += "?"
            if anchor_id:
                resource_url_fragment += f"id={anchor_id}"
                if insert_policy:
                    resource_url_fragment += "&"
            if insert_policy:
                resource_url_fragment += f"operation={insert_policy.value}"

        data = {}
        data['resource_type'] = "FirewallSection"
        data['display_name'] = name
        data['section_type'] = "LAYER3"
        if applied_tos:
            data['applied_tos'] = applied_tos
        if tags:
            data['tags'] = tags
        data['stateful'] = "true"
        data['enforced_on'] = "VIF"

        firewall_section = self._nsxt_client.do_request(
            method=RequestMethodVerb.POST,
            resource_url_fragment=resource_url_fragment,
            payload=data)

        return firewall_section

    def delete_firewall_section(self, name=None, id=None, cascade=True):
        """Delete a DFW Section identified by id or name.

        Identification by id takes precedence. Will return False if no matching
        NSGroup is found.

        :param str name: name of the DFW Section to be deleted..
        :param str id: id of the DFW Section to be deleted.
        :param bool cascade: if True, all rules in the section will be deleted
            along with the section.

        :return: True, if the delete operation is successful, else False.

        :rtype: bool
        """
        if not name and not id:
            return False

        if not id:
            fws = self.get_firewall_section(name, id)
            if fws:
                id = fws['id']
            else:
                self._nsxt_client.LOGGER.debug(
                    f"DFW Section : {name} not found. Unable to delete.")
                return False
        resource_url_fragment = f"firewall/sections/{id}"
        if cascade:
            resource_url_fragment += "?cascade=true"

        self._nsxt_client.do_request(
            method=RequestMethodVerb.DELETE,
            resource_url_fragment=resource_url_fragment)

        return True

    def get_all_rules_in_section(self, section_id):
        """."""
        if not section_id:
            return

        resource_url_fragment = f"firewall/sections/{section_id}/rules"
        try:
            response = self._nsxt_client.do_request(
                method=RequestMethodVerb.GET,
                resource_url_fragment=resource_url_fragment)
        except HTTPError as err:
            if err.response.status_code != 404:
                raise
            else:
                return

        rules = response['results']
        return rules

    def create_dfw_rule(self,
                        section_id,
                        rule_name,
                        source_nsgroup_id,
                        dest_nsgroup_id,
                        action,
                        anchor_rule_id=None,
                        insert_policy=None):
        """Create a new DFW Rule.

        :param str section_id: id of the section where the new rule will be
            added.
        :param str rule_name: name of the new rule to be created.
        :param str source_nsgroup_id: id of the source NSGroup.
        :param str dest_nsgroup_id: id of the destination NSGroup.
        :param constants.FIREWALL_ACTION action: action NSX-T should take once
            a rule is matched.
        :param str anchor_rule_id: id of another DFW Rule that will be used to
            figure out the position of the newly created DFW Rule.
        :param constants.INSERT_POLICY insert_policy: the relative position of
            the newly created rule to the anchor rule.

        :return: details of the newly created DFW Rule as a dictionary.

        :rtype: dict
        """
        section = self.get_firewall_section(id=section_id)

        resource_url_fragment = f"firewall/sections/{section_id}/rules"
        if anchor_rule_id or insert_policy:
            resource_url_fragment += "?"
            if anchor_rule_id:
                resource_url_fragment += f"id={anchor_rule_id}"
                if insert_policy:
                    resource_url_fragment += "&"
            if insert_policy:
                resource_url_fragment += f"operation={insert_policy.value}"

        data = {}
        data['display_name'] = rule_name
        data['destinations_excluded'] = "false"
        data['sources_excluded'] = "false"
        data['ip_protocol'] = "IPV4_IPV6"
        data['disabled'] = "false"
        data['direction'] = "IN_OUT"
        data['action'] = action.value
        data['_revision'] = section['_revision']

        source = {}
        source['target_type'] = "NSGroup"
        source['target_id'] = source_nsgroup_id
        data['sources'] = [source]

        destination = {}
        destination['target_type'] = "NSGroup"
        destination['target_id'] = dest_nsgroup_id
        data['destinations'] = [destination]

        rule = self._nsxt_client.do_request(
            method=RequestMethodVerb.POST,
            resource_url_fragment=resource_url_fragment,
            payload=data)

        return rule
