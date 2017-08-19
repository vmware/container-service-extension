# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging
from lxml import objectify
from pyvcloud.vcd.client import _WellKnownEndpoint
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
import requests
import time


LOGGER = logging.getLogger(__name__)


class Provisioner(object):

    def __init__(self, host, username, password, version, verify, log):
        self.host = host
        self.username = username
        self.password = password
        self.version = version
        self.verify = verify
        self.log = log
        self.client_sysadmin = None
        self.client_tenant = None

    def connect_sysadmin(self):
        if not self.verify:
            LOGGER.warning('InsecureRequestWarning: '
                           'Unverified HTTPS request is being made. '
                           'Adding certificate verification is strongly '
                           'advised.')
            requests.packages.urllib3.disable_warnings()
        self.client_sysadmin = Client(uri=self.host,
                                      api_version=self.version,
                                      verify_ssl_certs=self.verify,
                                      log_file='sysadmin.log',
                                      log_headers=True,
                                      log_bodies=True
                                      )
        self.client_sysadmin.set_credentials(
            BasicLoginCredentials(self.username,
                                  'System',
                                  self.password))

    def connect_tenant(self, body):
        token = body.get('headers').get('x-vcloud-authorization')
        accept_header = body.get('headers').get('Accept')
        version = accept_header.split('version=')[1]
        self.client_tenant = Client(uri=self.host,
                                    api_version=version,
                                    verify_ssl_certs=self.verify,
                                    log_file='tenant.log',
                                    log_headers=True,
                                    log_bodies=True
                                    )
        session = self.client_tenant.rehydrate_from_token(token)
        # print(client._get_wk_endpoint(_WellKnownEndpoint.LOGGED_IN_ORG))
        return {'user_name': session.get('user'), 'org_name': session.get('org')}

    def validate_name(self, name):
        """
        Validates that the cluster name against the pattern.
        """

        # TODO (validate against pattern)
        # pattern = '^[a-zA-Z](([-0-9a-zA-Z]+)?[0-9a-zA-Z])?(\.[a-zA-Z](([-0-9a-zA-Z]+)?[0-9a-zA-Z])?)*$'  # NOQA

        return True

    def search_by_name(self, name):
        """
        check that the cluster name exists in the current VDC.
        It exists, it returns the cluster id
        """
        return None

    def search_by_id(self, cluster_id):
        """
        check that the cluster with cluster_id exists in the current VDC.
        It exists, it returns the cluster name and details.
        """
        return None

    def create_cluster_thread(self, cluster_id):
        pass

    def delete_cluster_thread(self, cluster_id):
        pass
