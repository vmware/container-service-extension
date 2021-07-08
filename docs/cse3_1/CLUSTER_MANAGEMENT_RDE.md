---
layout: default
title: Kubernetes Cluster Management via API
---
<a name="cluster_management_api"></a>
# Kubernetes Cluster Management via API

Starting CSE 3.1, there are two ways to life cycle manage the native clusters via VCD API.
1. Generic defined entity API
2. Unified API endpoint for both Native and TKGs.

## Generic defined entity API:

The CRUD operations on native clusters can be invoked by using generic defined entity API.

Examples:
- POST `https://vcd-fqdn/cloudapi/1.0.0/entityTypes/urn:vcloud:type:cse:nativeCluster:2.0.0` 
  with the JSON formatted native payload embedded in the RDE. The task reference can be 
  retrieved from the Location header in the response.
  ```sh
  {
            "id": "urn:vcloud:entity:cse:nativeCluster:7b41afc8-4dc4-4fc6-a5b2-d91c677e9e5c",
            "entityType": "urn:vcloud:type:cse:nativeCluster:2.0.0",
            "name": "native1234567",
            "externalId": null,
            "entity": {
                "kind": "native",
                "spec": {
                    "settings": {
                        "ovdcNetwork": "ovdc_network",
                        "rollbackOnFailure": true
                    },
                    "topology": {
                        "workers": {
                            "count": 1
                        },
                        "controlPlane": {
                            "count": 1
                        }
                    },
                    "distribution": {
                        "templateName": "ubuntu-16.04_k8-1.18_weave-2.6.5",
                        "templateRevision": 2
                    }
                },
                "metadata": {
                    "name": "cluster_name",
                    "site": "",
                    "orgName": "cse-org",
                    "virtualDataCenterName": "cse-vdc"
                },
                "apiVersion": "cse.vmware.com/v2.0"
            }
        }
  }
  ```
- GET `https://vcd-fqdn/cloudapi/1.0.0/entities/urn:vcloud:entity:cse:nativeCluster:7b41afc8-4dc4-4fc6-a5b2-d91c677e9e5c` 
  will retrieve the native entity embedded in the RDE.
  
- PUT `https://vcd-fqdn/cloudapi/1.0.0/entities/urn:vcloud:entity:cse:nativeCluster:7b41afc8-4dc4-4fc6-a5b2-d91c677e9e5c` 
  with the JSON formatted native payload embedded in the RDE (same as the payload 
  of POST operation) can be used to resize or upgrade the cluster. The task reference 
  can be retrieved from the xvcloud-task-location header.
  
- DELETE `https://vcd-fqdn/cloudapi/1.0.0/entities/urn:vcloud:entity:cse:nativeCluster:7b41afc8-4dc4-4fc6-a5b2-d91c677e9e5c` 
  will delete the native entity. The task reference can be retrieved from the xvcloud-task-location header.
  
## Unified API endpoint for both native and TKGs

Refer to [VCD documentation](TODO) for more details.