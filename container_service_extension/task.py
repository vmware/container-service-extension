# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import logging
from provisioner import Provisioner
import threading
import time
import traceback

LOGGER = logging.getLogger(__name__)


def create_or_update_task(task,
                          operation_name,
                          operation_description,
                          cluster_name,
                          cluster_id,
                          status,
                          details,
                          provisioner,
                          task_id=None):
    namespace = 'cpsbu.cse'
    org_id = provisioner.vca_tenant.vcloud_session.org_id
    owner_href = 'urn:cse:cluster:%s' % cluster_id
    owner_name = cluster_name
    owner_type = 'application/cpsbu.cse.cluster+xml'
    progress = None
    status = status
    user_id = provisioner.vca_tenant.vcloud_session.user_id
    user_name = provisioner.vca_tenant.vcloud_session.username
    t = task.create_or_update_task(status,
                                   namespace,
                                   operation_name,
                                   operation_description,
                                   owner_href,
                                   owner_name,
                                   owner_type,
                                   user_id,
                                   user_name,
                                   progress,
                                   details,
                                   org_id=org_id,
                                   task_id=task_id)
    return t


class TaskThread(threading.Thread):

    def __init__(self, thread_id, config):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.config = config
        self.should_continue = True

    def stop(self):
        self.should_continue = False

    def run(self):
        try:
            vca_system = Provisioner.get_system_session(self.config)
            LOGGER.info(vca_system)
        except Exception:
            LOGGER.error(traceback.format_exc())


def update_task_thread(task,
                       operation_name,
                       operation_description,
                       cluster_name,
                       cluster_id,
                       status,
                       details,
                       provisioner,
                       cove,
                       task_id):
    det = json.loads(details)
    should_continue = True
    while should_continue:
        try:
            LOGGER.debug('update_task_thread %s:%s' %
                         (det['name'], det['cove_task_id']))
            cove_task = cove.get_task(det['cove_task_id'])
            cove_task_state = cove_task.stepInfos[-1]['state']
            LOGGER.debug('%s: %s' %
                         (det['cove_task_id'], cove_task_state))
            if cove_task_state in ['waiting', 'processing']:
                pass
            elif cove_task_state in ['completed', 'failed']:
                should_continue = False
                status = 'success' if cove_task_state == 'completed' \
                    else 'error'
            create_or_update_task(task,
                                  operation_name,
                                  operation_description,
                                  cluster_name,
                                  cluster_id,
                                  status,
                                  details,
                                  provisioner,
                                  task_id)
            if should_continue:
                time.sleep(2)
        except Exception:
            LOGGER.error(traceback.format_exc())
            break
