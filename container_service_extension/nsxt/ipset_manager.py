# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from constants import RequestMethodVerb


class IPSetManager(object):
    """."""

    def __init__(self, nsxt_client):
        self._nsxt_client = nsxt_client

    def get_ip_block_by_id(self, id):
        resource_url_fragment = f"pools/ip-blocks/{id}"

        ip_block = self._nsxt_client.do_request(
            method=RequestMethodVerb.GET,
            resource_url_fragment=resource_url_fragment)

        return ip_block

    def list_ip_sets(self):
        resource_url_fragment = "ip-sets"

        response = self._nsxt_client.do_request(
            method=RequestMethodVerb.GET,
            resource_url_fragment=resource_url_fragment)

        ip_sets = response['results']
        return ip_sets

    def get_ip_set(self, name=None, id=None):
        if name is None and id is None:
            return None

        ip_sets = self.list_ip_sets()
        for ip_set in ip_sets:
            if id is not None and ip_set['id'] == id:
                return ip_set
            if name is not None and ip_set['display_name'] == name:
                return ip_set

        return None

    def create_ip_set(self, ip_set_name, ip_addresses):
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
        ip_addresses = []
        for ip_block_id in ip_block_ids:
            ip_block = self.get_ip_block_by_id(ip_block_id)
            ip_addresses.append(ip_block['cidr'])
        return self.create_ip_set(ip_set_name, ip_addresses)
