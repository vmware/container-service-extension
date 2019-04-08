# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import requests

from container_service_extension.logger import configure_server_logger
from container_service_extension.nsxt.cluster_network_manager import \
    ClusterNetworkManager
from container_service_extension.nsxt.cse_nsxt_setup_utils import \
    setup_nsxt_constructs
from container_service_extension.nsxt.nsxt_client import NSXTClient

NSXT_HOST = '192.168.111.29'
NSXT_USERNAME = 'admin'
NSXT_PASSWORD = 'Admin!23Admin'

HTTP_PROXY = 'http://10.160.128.185:80'
HTTPS_PROXY = 'https://10.160.128.185:80'

NODES_IP_BLOCK_IDS = [
    '489f58b1-a7fa-4241-a7ec-69490d853878',
    '5764165b-7227-457a-a74d-c23872098bf7']
PODS_IP_BLOCK_IDS = [
    'e70b243d-423a-4813-a328-acd95244a2e0',
    '984cbf77-d611-400a-842d-81e47e8d7e95']
NCP_BOUNDARY_FIREWALL_SECTION_ANCHOR_ID = \
    '44f78f7c-c770-4a9f-b4f9-9062a89306e7'


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

    cluster_network_manager = ClusterNetworkManager(nsxt_client)

    cluster_id = 'f44766e9-a330-4a4a-a86e-5773c21968cb'
    cluster_name = 'cluster1'
    # cluster_network_manager.isolate_cluster(cluster_name, cluster_id)
    # cluster_network_manager.cleanup_cluster(cluster_name)

    cluster_id = '1c1d3ea4-c9e0-4b93-a8b1-0cb58b578048'
    cluster_name = 'cluster2'
    # cluster_network_manager.isolate_cluster(cluster_name, cluster_id)
    # cluster_network_manager.cleanup_cluster(cluster_name)
