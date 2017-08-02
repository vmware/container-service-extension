# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import time
from pyvcloud.task import Task
from pyvcloud.vcloudair import VCA
from pyvcloud.vcloudsession import VCS


LOGGER = logging.getLogger(__name__)


def wait_for_task(task, task_id):
    t = task.get_task(task_id)
    while t.get_status() != 'success':
        time.sleep(3)
        t = task.get_task(task_id)
        LOGGER.debug('%s, %s, %s, %s, %s, %s->%s' %
                     (t.get_id().split(':')[-1],
                      t.get_operation(),
                      t.get_Owner().get_name(),
                      t.get_status(),
                      t.get_Progress(),
                      str(t.get_startTime()).split('.')[0],
                      str(t.get_endTime()).split('.')[0]))


class Provisioner(object):

    def __init__(self, host, vcloud_token, version, verify, log=False):
        self.host = host
        self.vcloud_token = vcloud_token
        self.version = version
        self.verify = verify
        self.log = log
        self.vca_tenant = VCA(host=host, username='', service_type='vcd',
                              version=version, verify=verify, log=log)

    def connect(self):
        link = 'https://%s/api/session' % (self.host)
        vcloud_session = VCS(link, '', '', None, '', '',
                             version=self.version,
                             verify=self.verify,
                             log=self.log)
        result = vcloud_session.update_session_data(self.vcloud_token)
        if not result:
            LOGGER.error('unable to connect provisioner for token: %s' %
                         (self.vcloud_token))
            return False
        self.vca_tenant.vcloud_session = vcloud_session
        LOGGER.info('connected provisioner for: %s@%s (%s)' %
                    (self.vca_tenant.vcloud_session.username,
                     self.vca_tenant.vcloud_session.org,
                     self.vcloud_token))
        return True

    def get_task_status(self, task_id):
        try:
            task = Task(session=self.vca_tenant.vcloud_session,
                        verify=self.verify, log=self.log)
            t = task.get_task(task_id)
            return t.get_status()
        except:
            return 'unknown'

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
        result = {'name': name, 'cluster_id': None}

        return result

    def search_by_id(self, cluster_id):
        """
        check that the cluster with cluster_id exists in the current VDC.
        It exists, it returns the cluster name and details.
        """
        # result = {'name': None, 'cluster_id': cluster_id}
        result = {'name': cluster_id.split('-')[0], 'cluster_id': cluster_id}

        return result

    @staticmethod
    def get_system_session(config):
        vca_system = VCA(host=config['vcd']['host'],
                         username=config['vcd']['username'],
                         service_type='vcd',
                         version=config['vcd']['api_version'],
                         verify=config['vcd']['verify'],
                         log=config['vcd']['log'])

        org_url = 'https://%s/cloud' % config['vcd']['host']
        r = vca_system.login(password=config['vcd']['password'],
                             org='System',
                             org_url=org_url)
        if not r:
            raise Exception('failed to login as system')
        r = vca_system.login(token=vca_system.token,
                             org='System',
                             org_url=vca_system.vcloud_session.org_url)
        if not r:
            raise Exception('failed to login as system')
        return vca_system
