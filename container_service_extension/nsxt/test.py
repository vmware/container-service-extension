# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from cluster_manager import ClusterManager
from nsxt_client import NSXTClient
import requests
from setup import setup_nsxt_constructs

from container_service_extension.logger import configure_server_logger


NSXT_HOST = '192.168.111.143'
NSXT_USERNAME = 'admin'
NSXT_PASSWORD = 'Admin!23Admin'

HTTP_PROXY = 'http://10.160.113.17:80'
HTTPS_PROXY = 'https://10.160.113.17:80'

NODES_IP_BLOCK_IDS = [
    'a0a12cfd-1c30-423e-8d73-74ae0861a036',
    'eec2cbb8-6549-4cca-add5-9a8a6c46f5fd']
PODS_IP_BLOCK_IDS = [
    '352a3610-76e4-4bed-88ea-fedf679182ab',
    '47fb537d-69f2-4f9e-8300-c140276f5566']
NCP_BOUNDARY_FIREWALL_SECTION_ANCHOR_ID = \
    "38a86aea-8de0-4d7e-98d4-2551c9d3c6e7"


if __name__ == '__main__':
    requests.packages.urllib3.disable_warnings()
    configure_server_logger()

    nsxt_client = NSXTClient(
        host=NSXT_HOST,
        username=NSXT_USERNAME,
        password=NSXT_PASSWORD,
        http_proxy=HTTP_PROXY,
        https_proxy=HTTPS_PROXY,
        verify_ssl=False,
        log_requests=True,
        log_headers=True,
        log_body=False)

    setup_nsxt_constructs(
        nsxt_client=nsxt_client,
        nodes_ip_block_id=NODES_IP_BLOCK_IDS,
        pods_ip_block_id=PODS_IP_BLOCK_IDS,
        ncp_boundary_firewall_section_anchor_id=NCP_BOUNDARY_FIREWALL_SECTION_ANCHOR_ID)  # noqa

    cluster_manager = ClusterManager(nsxt_client)

    cluster_id = 'f44766e9-a330-4a4a-a86e-5773c21968cb'
    cluster_name = 'cluster1'
    cluster_manager.isolate_cluster(cluster_name, cluster_id)

    cluster_id = '1c1d3ea4-c9e0-4b93-a8b1-0cb58b578048'
    cluster_name = 'cluster2'
    cluster_manager.isolate_cluster(cluster_name, cluster_id)
