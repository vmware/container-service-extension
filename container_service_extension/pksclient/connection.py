# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.pksclient.configuration import Configuration
from container_service_extension.pksclient.api_client import ApiClient
from container_service_extension.pksclient.api.cluster_api import ClusterApi
from container_service_extension.uaaclient.uaaclient import UaaClient


uaaClient = UaaClient('https://api.pks.local:8443', 'admin', 'YtAU6Rl2dEvj1_hH9wEQxDUkxO1Lcjm3')
token = uaaClient.getToken()
print(token)

config = Configuration()
config.proxy = 'http://10.161.148.112:80'
config.host = 'https://api.pks.local:9021/v1'
config.access_token = token
config.username = 'admin'
config.verify_ssl = False

pksClient = ApiClient(configuration=config)

clusterApi = ClusterApi(api_client=pksClient)
clusters = clusterApi.list_clusters()
print(clusters)

