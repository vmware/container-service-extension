# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


class VC_Adapter(object):

    def __init__(self, vca_system, prov):
        self.vca_system = vca_system
        self.prov = prov

    def get_list_params(self):
        """
        Translates the input parameters identifying a list cluster operation in
        vCD/CSE to the input parameters required by KoV to list a cluster.
        It uses self.vca_system and self.prov to introspect vCD.

        :return: (result)
        """

        result = []
        return result


    def get_create_params(self, body):
        """
        Translates the input parameters identifying a cluster in vCD to
        the input parameters required by KoV to create a cluster.
        It uses self.vca_system and self.prov to introspect vCD.

        :return: (result)
        """

        result = {}

        cluster_name = body['name']
        node_count = body['node_count']
        vdc_name = body['vdc']
        network_name = body['network']

        request_username = self.prov.vca_tenant.vcloud_session.username
        request_org_id = self.prov.vca_tenant.vcloud_session.org_id

        return result

    def get_delete_params(self, body):
        """
        Translates the input parameters identifying a cluster in vCD to
        the input parameters required by KoV to delete a cluster.
        It uses self.vca_system and self.prov to introspect vCD.

        :return: (result)
        """

        result = {}
        return result
