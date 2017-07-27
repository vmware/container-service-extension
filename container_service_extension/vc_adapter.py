# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


class VC_Adapter(object):

    def __init__(self, config, vca_system, prov):
        self.config = config
        self.vca_system = vca_system
        self.prov = prov

    def get_list_params(self):
        """
        Translates the input parameters identifying a list cluster operation in
        vCD/CSE to the input parameters required by KoV to list clusters.
        It uses the global config, self.vca_system and self.prov to
        introspect vCD.

        :return: (result)
        """

        vcs = self.config['vcs'][0]

        return vcs

    def get_create_params(self, body, cluster_id):
        """
        Translates the input parameters identifying a cluster in vCD to
        the input parameters required by KoV to create a cluster.
        It uses self.vca_system and self.prov to introspect vCD.
        The result should also include the vCenter information.

        :return: (result)
        """

        # vdc_name = body['vdc']
        # request_username = self.prov.vca_tenant.vcloud_session.username
        # request_org_id = self.prov.vca_tenant.vcloud_session.org_id

        vcs = self.config['vcs'][0]

        params = {
                    "name": 'c-' + cluster_id,
                    "cloudProvider": "vsphere",
                    "datacenter": vcs['datacenter'],
                    "datastore": vcs['datastore'],
                    "maxNodes": body['node_count'],
                    "minNodes": body['node_count'],
                    "noOfMasters": 1,
                    "nodeNetwork": vcs['network'],
                    "managementNetwork": vcs['network'],
                    "opsUsername": vcs['username'],
                    "opsPassword": vcs['password'],
                    "vsphereCluster": vcs['cluster'],
                    "authorizedKeys": []
                 }

        # params = {
        #             "name": 'c-' + cluster_id,
        #             "minNodes": body['node_count'],
        #             "maxNodes": body['node_count'],
        #             "authorizedKeys": [],
        #             "vsphere": {
        #                 "datacenter": vcs['datacenter'],
        #                 "computeResource": vcs['cluster'],
        #                 "datastore": vcs['datastore'],
        #                 "publicNetwork": vcs['network'],
        #                 "opsUsername": vcs['username'],
        #                 "opsPassword": vcs['password'],
        #             }
        #          }

        return (vcs, params)

    def get_delete_params(self, body, cluster_id):
        """
        Translates the input parameters identifying a cluster in vCD to
        the input parameters required by KoV to delete a cluster.
        It uses self.vca_system and self.prov to introspect vCD.
        The result should also include the vCenter information.

        :return: (result)
        """

        vcs = self.config['vcs'][0]
        return(vcs, 'c-'+cluster_id)
