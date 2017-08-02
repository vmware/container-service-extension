# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging

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
