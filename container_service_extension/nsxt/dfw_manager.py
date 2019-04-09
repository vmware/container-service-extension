# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from requests.exceptions import HTTPError

from container_service_extension.logger import SERVER_NSXT_LOGGER as LOGGER
from container_service_extension.nsxt.constants import RequestMethodVerb


class DFWManager(object):
    """."""

    def __init__(self, nsxt_client):
        self._nsxt_client = nsxt_client

    def list_firewall_sections(self):
        resource_url_fragment = "firewall/sections"

        response = self._nsxt_client.do_request(
            method=RequestMethodVerb.GET,
            resource_url_fragment=resource_url_fragment)

        firewall_sections = response['results']
        return firewall_sections

    def get_firewall_section(self, name=None, id=None):
        if not name and not id:
            return None

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

        return None

    def create_firewall_section(self,
                                name,
                                applied_tos=None,
                                tags=None,
                                anchor_id=None,
                                insert_policy=None):
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
        if not name and not id:
            return False

        if not id:
            fws = self.get_firewall_section(name, id)
            if fws:
                id = fws['id']
            else:
                LOGGER.debug(
                    f"DFW Section : {name} not found. Unable to delete.")
                return False
        resource_url_fragment = f"firewall/sections/{id}"
        if cascade:
            resource_url_fragment += "?cascade=true"

        self._nsxt_client.do_request(
            method=RequestMethodVerb.DELETE,
            resource_url_fragment=resource_url_fragment)

        return True

    def create_dfw_rule(self,
                        section_id,
                        rule_name,
                        source_nsgroup_id,
                        dest_nsgroup_id,
                        action,
                        anchor_rule_id=None,
                        insert_policy=None):
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
