---
layout: default
title: Kubernetes Cluster Management
---
# Kubernetes Cluster Management

<a name="overview"></a>
## Overview

This page shows basic commands that allow tenants to create, manage,
and remove Kubernetes clusters using CSE. The primary tool for these
operations is the `vcd cse` client command.

<a name="useful_commands"></a>
## Useful Commands
`vcd cse ...` commands are used by tenant organization administrators and tenant users to:
- List templates
- Get CSE server status
- Create, list, info, delete clusters/nodes

Here is a summary of commands available to view templates and manage clusters and nodes:

**CSE server configured against VCD 10.3.z, 10.2.z in non legacy mode**

| Command                                                                | Description                                                                | Native | TKG |
|------------------------------------------------------------------------|----------------------------------------------------------------------------|--------|-----|
| `vcd cse template list`                                                | List templates that a Kubernetes cluster can be deployed from.             | Yes    | Yes |
| `vcd cse cluster apply CLUSTER_CONFIG.YAML`                            | Create or update a Kubernetes cluster.                                     | Yes    | Yes |
| `vcd cse cluster list`                                                 | List available Kubernetes clusters.                                        | Yes    | Yes |
| `vcd cse cluster info CLUSTER_NAME`                                    | Retrieve detailed information of a Kubernetes cluster.                     | Yes    | Yes |
| `vcd cse cluster config CLUSTER_NAME`                                  | Retrieve the kubectl configuration file of the Kubernetes cluster.         | Yes    | Yes |
| `vcd cse cluster delete CLUSTER_NAME`                                  | Delete a Kubernetes cluster.                                               | Yes    | Yes |
| `vcd cse cluster delete CLUSTER_NAME --force`                          | Delete a Kubernetes cluster even if they are in an unrecoverable state.    | Yes    | Yes |
| `vcd cse cluster upgrade-plan CLUSTER_NAME`                            | Retrieve the allowed path for upgrading Kubernetes software on the custer. | Yes    | No  |
| `vcd cse cluster upgrade CLUSTER_NAME TEMPLATE_NAME TEMPLATE_REVISION` | Upgrade cluster software to specified template's software versions.        | Yes    | No  |
| `vcd cse cluster delete-nfs CLUSTER_NAME NFS_NODE_NAME`                | Delete NFS node of a given Kubernetes cluster                              | Yes    | No  |
| `vcd cse cluster share --name CLUSTER_NAME --acl FullControl USER1`    | Share cluster 'mycluster' with FullControl access with 'user1'             | Yes    | No  |
| `vcd cse cluster share-list --name CLUSTER_NAME`                       | View the acl info for a cluster.                                           | Yes    | No  |
| `vcd cse cluster unshare --name CLUSTER_NAME USER1`                    | Unshare the cluster with the user1.                                        | Yes    | No  |


**CSE server configured against VCD 10.3.z, 10.2.z, 10.1.z in legacy mode**

| Command                                                                | Description                                                                |
|------------------------------------------------------------------------|----------------------------------------------------------------------------|
| `vcd cse template list`                                                | List templates that a Kubernetes cluster can be deployed from.             |
| `vcd cse cluster create CLUSTER_NAME`                                  | Create a new Kubernetes cluster.                                           |
| `vcd cse cluster create CLUSTER_NAME --enable-nfs`                     | Create a new Kubernetes cluster with NFS Persistent Volume support.        |
| `vcd cse cluster list`                                                 | List available Kubernetes clusters.                                        |
| `vcd cse cluster info CLUSTER_NAME`                                    | Retrieve detailed information of a Kubernetes cluster.                     |
| `vcd cse cluster resize CLUSTER_NAME`                                  | Grow a Kubernetes cluster by adding new nodes.                             |
| `vcd cse cluster config CLUSTER_NAME`                                  | Retrieve the kubectl configuration file of the Kubernetes cluster.         |
| `vcd cse cluster upgrade-plan CLUSTER_NAME`                            | Retrieve the allowed path for upgrading Kubernetes software on the custer. |
| `vcd cse cluster upgrade CLUSTER_NAME TEMPLATE_NAME TEMPLATE_REVISION` | Upgrade cluster software to specified template's software versions.        |
| `vcd cse cluster delete CLUSTER_NAME`                                  | Delete a Kubernetes cluster.                                               |
| `vcd cse node create CLUSTER_NAME --nodes n`                           | Add `n` nodes to a Kubernetes cluster.                                     |
| `vcd cse node create CLUSTER_NAME --nodes n --enable-nfs`              | Add an NFS node to a Kubernetes cluster.                                   |
| `vcd cse node list CLUSTER_NAME`                                       | List nodes of a cluster.                                                   |
| `vcd cse node info CLUSTER_NAME NODE_NAME`                             | Retrieve detailed information of a node in a Kubernetes cluster.           |
| `vcd cse node delete CLUSTER_NAME NODE_NAME`                           | Delete nodes from a cluster.                                               |
| `vcd cse node list CLUSTER_NAME`                                       | List nodes of a cluster.                                                   |
| `vcd cse node info CLUSTER_NAME NODE_NAME`                             | Retrieve detailed information of a node in a Kubernetes cluster.           |
| `vcd cse node delete CLUSTER_NAME NODE_NAME`                           | Delete nodes from a cluster.                                               |

<a name="cse31_cluster_apply"></a>
### CSE 3.1 `Cluster apply` command

1. `vcd cse cluster apply <create_cluster.yaml>` command - Takes a cluster 
   specification file as an input and applies it to a cluster resource. The 
   cluster resource will be created if it does not exist. It can be used to create 
   the cluster, scale up/down workers, scale up NFS nodes, upgrade the cluster to a new K8s version.
    * Note that a new property `spec.settings.network.expose` can be used to 
      expose the cluster to the external world. This would require user to have 
      EDIT rights on edge gateway. Refer to [expose cluster](#expose_cluster) for more details.
    * Command usage examples:
        ```
        vcd cse cluster apply <create_cluster.yaml> (creates the cluster if the resource already does not exist.)
        vcd cse cluster apply <resize_cluster.yaml> (resizes the specification on the resource specified). 
        vcd cse cluster apply <upgrade_cluster.yaml> (upgrades the cluster to match the user specified template and revision)
        vcd cse cluster apply --sample --tkg-s (generates the sample specification file for tkg-s clusters).
        vcd cse cluster apply --sample --tkg (generates the sample specification file for tkg clusters).
        vcd cse cluster apply --sample --native (generates the sample specification file for native clusters).
        ```
    * How to construct the specification for the cluster creation?
        - Get a sample native cluster specification from `vcd cse cluster apply -s -n`.
        - Populate the required properties. Note that the sample file has detailed comments to identify the required and optional properties.
        - Run `vcd cse cluster apply <create_cluster.yaml>`
  
    * How to construct the specification for the update operation (scale-up/down workers, K8 upgrade, scale-up NFS node) ?
      - Retrieve the current status of the cluster: Save the result of `vcd cse cluster info` for further editing.
      - Update the saved specification with the current status of the cluster:
        - update the `spec` section with the accurate values provided in `status` section. 
          Note that the `status` section of the output is what actually represents 
          the true current state of the cluster and `spec`portion of the result 
          just represents the latest desired state expressed by the user. For example, 
          the current count of `status.nodes.workers` could be different from the 
          `spec.topology.workers.count` because of the potential failure in the previous resize operation.
      - Update the new specification with the desired status of the cluster:
        - update the `spec` with the new desired state of the cluster. Note that 
          you can only update few properties: scale-up/down (`spec.topology.workers.count`), 
          scale-up nfs (`spec.topology.nfs.count`), and upgrade (`spec.distribution.templateName` and `spec.distribution.templateRevision`).
      - Save the file as `update_cluster.yaml` and issue the command `vcd cse cluster apply update_cluster.yaml`
      
    * Sample input specification file
        ```sh
        # Short description of various properties used in this sample cluster configuration
        # apiVersion: Represents the payload version of the cluster specification. By default, "cse.vmware.com/v2.0" is used.
        # kind: The kind of the Kubernetes cluster.
        #
        # metadata: This is a required section
        # metadata.name: Name of the cluster to be created or resized.
        # metadata.orgName: The name of the Organization in which cluster needs to be created or managed.
        # metadata.virtualDataCenterName: The name of the Organization Virtual data center in which the cluster need to be created or managed.
        # metadata.site: VCD site domain name where the cluster should be deployed.
        #
        # spec: User specification of the desired state of the cluster.
        # spec.topology.controlPlane: An optional sub-section for desired control-plane state of the cluster. The properties "sizingClass" and "storageProfile" can be specified only during the cluster creation phase. These properties will no longer be modifiable in further update operations like "resize" and "upgrade".
        # spec.topology.controlPlane.count: Number of control plane node(s). Only single control plane node is supported.
        # spec.topology.controlPlane.sizingClass: The compute sizing policy with which control-plane node needs to be provisioned in a given "ovdc". The specified sizing policy is expected to be pre-published to the given ovdc.
        # spec.topology.controlPlane.storageProfile: The storage-profile with which control-plane needs to be provisioned in a given "ovdc". The specified storage-profile is expected to be available on the given ovdc.
        #
        # spec.distribution: This is a required sub-section.
        # spec.distribution.templateName: Template name based on guest OS, Kubernetes version, and the Weave software version
        # spec.distribution.templateRevision: revision number
        #
        # spec.topology.nfs: Optional sub-section for desired nfs state of the cluster. The properties "sizingClass" and "storageProfile" can be specified only during the cluster creation phase. These properties will no longer be modifiable in further update operations like "resize" and "upgrade".
        # spec.topology.nfs.count: Nfs nodes can only be scaled-up; they cannot be scaled-down. Default value is 0.
        # spec.topology.nfs.sizingClass: The compute sizing policy with which nfs node needs to be provisioned in a given "ovdc". The specified sizing policy is expected to be pre-published to the given ovdc.
        # spec.topology.nfs.storageProfile: The storage-profile with which nfs needs to be provisioned in a given "ovdc". The specified storage-profile is expected to be available on the given ovdc.
        #
        # spec.settings: This is a required sub-section
        # spec.settings.ovdcNetwork: This value is mandatory. Name of the Organization's virtual data center network
        # spec.settings.rollbackOnFailure: Optional value that is true by default. On any cluster operation failure, if the value is set to true, affected node VMs will be automatically deleted.
        # spec.settings.sshKey: Optional ssh key that users can use to log into the node VMs without explicitly providing passwords.
        # spec.settings.network.expose: Optional value that is false by default. Set to true to enable access to the cluster from the external world.
        #
        # spec.topology.workers: Optional sub-section for the desired worker state of the cluster. The properties "sizingClass" and "storageProfile" can be specified only during the cluster creation phase. These properties will no longer be modifiable in further update operations like "resize" and "upgrade". Non uniform worker nodes in the clusters is not yet supported.
        # spec.topology.workers.count: number of worker nodes (default value:1) Worker nodes can be scaled up and down.
        # spec.topology.workers.sizingClass: The compute sizing policy with which worker nodes need to be provisioned in a given "ovdc". The specified sizing policy is expected to be pre-published to the given ovdc.
        # spec.topology.workers.storageProfile: The storage-profile with which worker nodes need to be provisioned in a given "ovdc". The specified storage-profile is expected to be available on the given ovdc.
        #
        # status: Current state of the cluster in the server. This is not a required section for any of the operations.

        apiVersion: cse.vmware.com/v2.0
        kind: native
        metadata:
          name: cluster_name
          orgName: organization_name
          site: VCD_site
          virtualDataCenterName: org_virtual_data_center_name
        spec:
          distribution:
            templateName: ubuntu-16.04_k8-1.17_weave-2.6.0
            templateRevision: 2
          settings:
            network:
              expose: false
            ovdcNetwork: ovdc_network_name
            rollbackOnFailure: true
            sshKey: null
          topology:
            controlPlane:
              count: 1
              sizingClass: Large_sizing_policy_name
              storageProfile: Gold_storage_profile_name
            nfs:
              count: 0
              sizingClass: Large_sizing_policy_name
              storageProfile: Platinum_storage_profile_name
            workers:
              count: 2
              sizingClass: Medium_sizing_policy_name
              storageProfile: Silver_storage_profile
        ```
      
<a name="cse31_cluster_share"></a>
### CSE 3.1 `Cluster share` command
The `vcd cse cluster share` command is supported for both TKG-S and native clusters. 
- Sharing TKG-s clusters would simply share the corresponding RDEs with the other user(s).
- Sharing native clusters would share both the corresponding RDE and the backing vapp with the other user(s).
  
   ```sh
      # Share cluster 'mycluster' with FullControl access with 'user1' and 'user2'
      vcd cse cluster share --name mycluster --acl FullControl user1 user2
      
      # Share TKG cluster with cluster ID 'urn:vcloud:entity:vmware:tkgcluster:1.0.0:uuid' with ReadOnly access with 'user1'
      vcd cse cluster share --id urn:vcloud:entity:vmware:tkgcluster:1.0.0:uuid --acl ReadOnly user1  
      
      # View the acl info for a cluster; for each user the cluster is shared with, 
      # the user's access level, member id, and user name are listed.
      vcd cse cluster share-list --name cluster1
   
      # Unshare the cluster with a given user.
      vcd cse cluster unshare --name CLUSTER_NAME USER1
   ```
      
<a name="k8s_upgrade"></a>
## Upgrading software installed on Native Kubernetes clusters
Kubernetes is a fast paced piece of software, which gets a new minor release
every three months and numerous patch releases (including security patches) in
between those minor releases. To keep already deployed clusters up to date, in
CSE 2.6.0 we have added support for in place software upgrade for Kubernetes
clusters. The softwares that can be upgraded to a newer version are
* Kubernetes components e.g. kube-server, kubelet, kubedns etc.
* Weave (CNI)
* Docker engine

The upgrade matrix is built on the CSE native templates (read more about them
[here](TEMPLATE_MANAGEMENT.html)). The template
originally used to deploy a cluster determines the valid target templates for
upgrade. The supported upgrade paths can be discovered using the following command

```sh
vcd cse cluster upgrade-plan 'mycluster'
```

Let's say our cluster was deployed using template T1 which is based off
Kubernetes version `x.y.z`. Our potential target templates for upgrade will
satisfy at least one of the following criteria:
* A later revision of the template T1, which is based off Kubernetes version
  `x.y.`**`w`**, where `w` > `z`.
* A template T2 that has the same base OS, and is based off Kubernetes
  distribution `x.`**`(y+1)`**`.v`, where `v` can be anything.

If you don't see a desired target template for upgrading your cluster, please
feel free to file a GitHub [issue ](https://github.com/vmware/container-service-extension/issues).


The actual upgrade of the cluster is done via the following command.
```sh
vcd cse cluster upgrade 'mycluster'
```

The upgrade process needs little to zero downtime, if the following conditions
are met,
1. Docker is not being upgraded.
2. Weave (CNI) is not being upgraded.
3. Kubernetes version upgrade is restricted to patch version only.

If any of the conditions mentioned above is not met, the cluster will go down
for about a minute or more (depends on the actual upgrade process).

<a name="expose_cluster"></a>
## Creating clusters in Organizations with routed OrgVDC networks backed by NSX-T
Traditionally, CSE requires a directly connected OrgVDC network for K8s cluster deployment.
This is to make sure that the cluster VMs are reachable from outside the scope of the
OrgVDC network. With NSX-T, directly connected OrgVDC networks are not offered and
routed OrgVDC networks are used to deploy K8s clusters. In order to grant Internet access
to the cluster VMs connected to NSX-T backed routed OrgVDC networks, and maintain
accessibility to the clusters, CSE 3.0.2 offers an option to `expose` the cluster.

Users deploying clusters must have the following rights, if they want to leverage
the `expose` functionality.

* Gateway View
* NAT View Only
* NAT Configure

If even one of these rights are missing, CSE will ignore the request to expose the K8s cluster.

User can `expose` their K8s cluster during the first `vcd cse cluster apply`
command by specifying `expose : True` under `spec` section in the cluster
specification file. It should be noted that any attempt to expose the cluster after it has
been created will be ignored by CSE. Once a cluster has been exposed, the `status`
section of the cluster would show a new field viz. `exposed`, which would be set to `True`.


Users can de-`expose` a cluster, by setting the value of `expose` field to `False`
and applying the updated specification on the cluster via `vcd cse cluster apply`.
The value for the `exposed` field would be `False` for clusters that are not exposed.
An exposed cluster if ever de-exposed can't be re-exposed.

<a name="tkgm_clusters"></a>
## Creating clusters with VMware Tanzu Kubernetes Grid
Starting CSE 3.1.1, VMware Tanzu Kubernetes Grid (TKG) clusters can be deployed
like Native clusters using `vcd cse cluster apply` command. TKG cluster
specification file differs from a native cluster specification file
in the value of the fields `kind` and `template_name`. Sample file for
TKG cluster deployment can be generated using the following command
```
vcd cse cluster apply --sample --tkg
```

**Please note:**
* Routability of external network traffic to the cluster is crucial for VCD CPI to work.
Therefore, it is mandatory to deploy TKG clusters with `expose` field set to `True`.
Read more about expose functionality [here](CLUSTER_MANAGEMENT.html#expose_cluster).

* Users deploying VMware Tanzu Kubernetes Grid clusters should have the rights required
to deploy `exposed` native clusters and additionally the right `Full Control: CSE:NATIVECLUSTER`.
This right is crucial for VCD CPI to work properly. [CPI for VCD](https://github.com/vmware/cloud-provider-for-cloud-director/blob/1.0.0/README.md)
and [CSI for VCD](https://github.com/vmware/cloud-director-named-disk-csi-driver/blob/1.0.0/README.md)
docs list down all rights required for their proper functioning.

* VMware Tanzu Kubernetes Grid clusters should be connected to a network that can access
the public end point of the VCD. This network **should** have DNS setup, the same DNS server
would be used by all cluster vms for name resolution while reaching out to internet to
download Antrea, VCD CPI and VCD CSI.

* Scaling down TKG clusters is not supported. If users wish to shrink their TKG clusters, they need to use `kubectl` to do it.
  * On control plane node
    * `kubetcl cordon [node name]`
    * `kubectl drain [node name]`
    * `kubectl delete [node name]` (Optional, VCD CPI will update the state of the cluster once the actual worker VM is deleted)
  * On worker node
    * Once the commands on control plane node have successfully completed,
      power off the vm and delete it from VCD UI

* NFS based Persistent Volumes are not supported for TKG clusters.
Please use CSI for VCD to work with static and dynamic persistent volumes for K8s applications.

* Cluster sharing is not supported for TKG clusters.

* Kubernetes upgrade is not supported for TKG clusters.
