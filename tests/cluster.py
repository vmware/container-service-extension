# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.test import TestCase

from container_service_extension.client.cluster import Cluster


class TestCluster(TestCase):
    def test_01_template_list(self):
        logged_in_org = self.client.get_org()
        assert self.config['vcd']['org'] == logged_in_org.get('name')
        cluster = Cluster(self.client)
        templates = cluster.get_templates()
        assert len(templates) > 0

    def test_02_cluster_create(self):
        logged_in_org = self.client.get_org()
        assert self.config['vcd']['org'] == logged_in_org.get('name')
        cluster = Cluster(self.client)
        result = cluster.create_cluster(self.config['vcd']['vdc'],
                                        self.config['vcd']['network'],
                                        self.config['vcd']['cluster_name'])
        task = self.client.get_resource(result['task_href'])
        task = self.client.get_task_monitor().wait_for_status(task)
        assert task.get('status') == TaskStatus.SUCCESS.value

    def test_03_cluster_list(self):
        logged_in_org = self.client.get_org()
        assert self.config['vcd']['org'] == logged_in_org.get('name')
        cluster = Cluster(self.client)
        clusters = cluster.get_clusters()
        assert len(clusters) == 1

    def test_04_cluster_delete(self):
        logged_in_org = self.client.get_org()
        assert self.config['vcd']['org'] == logged_in_org.get('name')
        cluster = Cluster(self.client)
        result = cluster.delete_cluster(self.config['vcd']['cluster_name'])
        task = self.client.get_resource(result['task_href'])
        task = self.client.get_task_monitor().wait_for_status(task)
        assert task.get('status') == TaskStatus.SUCCESS.value

    def test_05_cluster_list(self):
        logged_in_org = self.client.get_org()
        assert self.config['vcd']['org'] == logged_in_org.get('name')
        cluster = Cluster(self.client)
        clusters = cluster.get_clusters()
        assert len(clusters) == 0


if __name__ == '__main__':
    unittest.main()
