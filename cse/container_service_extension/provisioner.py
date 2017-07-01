# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging, time
from pyvcloud.vcloudair import VCA
from pyvcloud.vcloudsession import VCS
from pyvcloud.task import Task

def wait_for_task(task, task_id):
    t = task.get_task(task_id)
    while t.get_status() != 'success':
        time.sleep(3)
        t = task.get_task(task_id)
        print('%s, %s, %s, %s, %s, %s->%s' % (t.get_id().split(':')[-1], t.get_operation(), t.get_Owner().get_name(), t.get_status(), t.get_Progress(), str(t.get_startTime()).split('.')[0], str(t.get_endTime()).split('.')[0]))

class Provisioner(object):

    def __init__(self, host, vcloud_token, version, verify, logger, log=False):
        self.host = host
        self.vcloud_token = vcloud_token
        self.version = version
        self.verify = verify
        self.logger = logger
        self.log = log
        self.vca_tenant = VCA(host=host, username='', service_type='vcd', version=version, verify=verify, log=log)

    def connect(self):
        link = 'https://%s/api/session' % (self.host)
        vcloud_session = VCS(link, '', '', None, '', '', version=self.version, verify=self.verify, log=self.log)
        result = vcloud_session.update_session_data(self.vcloud_token)
        if not result:
            self.logger.error('unable to connect provisioner for token: %s' % (self.vcloud_token))
            return False
        self.vca_tenant.vcloud_session = vcloud_session
        self.logger.info('connected provisioner for: %s@%s (%s)' % (self.vca_tenant.vcloud_session.username, self.vca_tenant.vcloud_session.org, self.vcloud_token))
        return True
