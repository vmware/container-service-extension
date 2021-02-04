# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from requests.exceptions import HTTPError

from container_service_extension.lib.nsxt.constants import RequestMethodVerb


class IPSetManager(object):
    """Facilitate Create, Retrieve operations on IPSets."""

    def __init__(self, nsxt_client):
        """Initialize a IPSetManager object.

        :param NSXTCLient nsxt_client: client to make NSX-T REST requests.
        """
        self._nsxt_client = nsxt_client

    def get_ip_block_by_id(self, id):
        """Get details of an IPBlock.

        :param str id: id of the IPBlock whose details are to be retrieved.

        :return: details of the IPBlock as a dictionary.

        :rtype: dict
        """
        resource_url_fragment = f"pools/ip-blocks/{id}"

        ip_block = self._nsxt_client.do_request(
            method=RequestMethodVerb.GET,
            resource_url_fragment=resource_url_fragment)

        return ip_block

    def list_ip_sets(self):
        """List all IPSets.

        :return: All IPSets in the system as a list of dictionaries, where
            each dictionary represent a IPSet.

        :rtype: list
        """
        resource_url_fragment = "ip-sets"

        response = self._nsxt_client.do_request(
            method=RequestMethodVerb.GET,
            resource_url_fragment=resource_url_fragment)

        ip_sets = response['results']
        return ip_sets

    def get_ip_set(self, name=None, id=None):
        """Get information of a IPSet identified by id or name.

        Identification by id takes precedence. Will return None if no matching
        IPSet is found.

        :param str name: name of the IPSet whose details are to be retrieved.
        :param str id: id of the IPSet whose details are to be retrieved.

        :return: details of the IPSet as a dictionary.

        :rtype: dict

        :raises HTTPError: If the underlying REST call fails with any status
            code other than 404.
        """
        if not name and not id:
            return

        if id:
            resource_url_fragment = f"ip-sets/{id}"
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

        ip_sets = self.list_ip_sets()
        for ip_set in ip_sets:
            if ip_set['display_name'].lower() == name.lower():
                return ip_set

    def create_ip_set(self, ip_set_name, ip_addresses):
        """Create a new NSGroup.

        :param str ip_set_name: name of the IPSet to be created.
        :param list ip_addresses: list of strings. Where each entry
            represents an ip address (can even be a range of ip addresses as
            CIDR).

        :return: details of the newly created IPSet as a dictionary.

        :rtype: dict
        """
        resource_url_fragment = "ip-sets"

        data = {}
        data['display_name'] = ip_set_name
        data['ip_addresses'] = ip_addresses

        ip_set = self._nsxt_client.do_request(
            method=RequestMethodVerb.POST,
            resource_url_fragment=resource_url_fragment,
            payload=data)

        return ip_set

    def create_ip_set_from_ip_block(self, ip_set_name, ip_block_ids):
        """Create a new IPSet.

        :param str ip_set_name: name of the IPSet to be created.
        :param list ip_block_ids: list of strings. Where each entry
            represents an IPBlock's id.

        :return: details of the newly created IPSet as a dictionary.

        :rtype: dict
        """
        ip_addresses = []
        for ip_block_id in ip_block_ids:
            ip_block = self.get_ip_block_by_id(ip_block_id)
            ip_addresses.append(ip_block['cidr'])
        return self.create_ip_set(ip_set_name, ip_addresses)
