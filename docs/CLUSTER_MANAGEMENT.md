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

Here is an overview of the process that a tenant administrator might
go through to install `vcd cse` and create a cluster. It includes
some internals of CSE so that you can understand what is happening
behind the covers.

![cse-usage](img/cse-usage-example.png)

CSE Kubernetes clusters can include persistent volumes mounted on NFS.
Procedures for creating and managing NFS nodes can be found at
[NFS Node Management](/container-service-extension/NFS_STATIC_PV.html).

<a name="useful_commands"></a>
## Useful Commands
`vcd cse ...` commands are used by tenant organization administrators and users to:
- list templates
- get CSE server status
- create, list, info, delete clusters/nodes

Here is a summary of commands available to view templates and manage clusters and nodes:

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
| `vcd cse node create CLUSTER_NAME --type nfsd`                         | Add an NFS node to a Kubernetes cluster.                                   |
| `vcd cse node list CLUSTER_NAME`                                       | List nodes of a cluster.                                                   |
| `vcd cse node info CLUSTER_NAME NODE_NAME`                             | Retrieve detailed information of a node in a Kubernetes cluster.           |
| `vcd cse node delete CLUSTER_NAME NODE_NAME`                           | Delete nodes from a cluster.                                               |

By default, CSE Client will display the task progress until the
task finishes or fails. The `--no-wait` flag can be used to skip waiting on the
task. CSE client will still show the task information of console, and end user
can choose to monitor the task progress manually.

```sh
> vcd --no-wait cse cluster create CLUSTER_NAME --network intranet --ssh-key ~/.ssh/id_rsa.pub

# displays the status and progress of the task
> vcd task wait 377e802d-f278-44e8-9282-7ab822017cbd

# lists the current running tasks in the organization
> vcd task list running
```

<a name="k8s_upgrade"></a>
## Upgrading software installed on Kubernetes clusters
Kubernetes is a fast paced piece of software, which gets a new minor release
every three months and numerous patch releases (including security patches) in
between those minor releases. To keep already deployed clusters up to date, in
CSE 2.6.0 we have added support for in place software upgrade for Kubernetes
clusters. The softwares that can be upgraded to a newer version are
* Kuberenetes components e.g. kube-server, kubelet, kubedns etc.
* Weave (CNI)
* Docker engine

The upgrade matrix is built on the CSE native templates (read more about them
[here](/container-service-extension/TEMPLATE_MANAGEMENT.html)). The template
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

<a name="automation"></a>
## Automation
`vcd cse` commands can be scripted to automate the creation and operation
of Kubernetes clusters and nodes.

Users can interact with CSE via the Python package (container-service-extension)
or the CSE REST API exposed via vCD.

This following Python script creates a Kubernetes cluster on vCloud Director:
```python
#!/usr/bin/env python3
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from container_service_extension.client.cluster import Cluster

client = Client('vcd.mysp.com')
client.set_credentials(BasicLoginCredentials('usr1', 'org1', '******'))

cse = Cluster(client)
result= cse.create_cluster('vdc1', 'net1', 'cluster1')
task = client.get_resource(result['task_href'])
task = client.get_task_monitor().wait_for_status(task)
print(task.get('status'))

client.logout()
```

<a name="example"></a>
## Example Use Case

```sh
# create cluster mycluster with one master and two nodes, connected to provided network
# a public key is provided to be able to ssh into the VMs
> vcd cse cluster create mycluster --network intranet --ssh-key ~/.ssh/id_rsa.pub

# list the worker nodes of a cluster
> vcd cse node list mycluster

# create cluster mycluster with one master, three nodes and connected to provided network
> vcd cse cluster create mycluster --network intranet --nodes 3 --ssh-key ~/.ssh/id_rsa.pub

# create a single worker node cluster, connected to the specified network. Nodes can be added later
> vcd cse cluster create mycluster --network intranet --nodes 0 --ssh-key ~/.ssh/id_rsa.pub

# create cluster mycluster with one master, three worker nodes, connected to provided network
# and one node of type NFS server
> vcd cse cluster create mycluster --network intranet --nodes 3 --ssh-key ~/.ssh/id_rsa.pub --enable-nfs

# add 2 worker nodes to a cluster with 4GB of ram and 4 CPUs each, from a photon template,
# using the specified storage profile
> vcd cse node create mycluster --nodes 2 --network intranet --ssh-key ~/.ssh/id_rsa.pub --memory 4096 --cpu 4 --template-name sample_photon_template --template-revision 1 --storage-profile sample_storage_profile

# add 1 nfsd node to a cluster with 4GB of ram and 4 CPUs each, from a photon template,
# using the specified storage profile
> vcd cse node create mycluster --nodes 1 --type nfsd --network intranet --ssh-key ~/.ssh/id_rsa.pub --memory 4096 --cpu 4 --template-name sample_photon_template --template-revision 1 --storage-profile sample_storage_profile

# resize the cluster to have 8 worker node. If resize fails, the cluster is returned to it's original size.
# '--network' is only applicable for clusters using native (vCD) Kubernetes provider.
> vcd cse cluster resize mycluster --network mynetwork --nodes 8

# info on a given node. If the node is of type nfsd, it displays info about Exports.
> vcd cse node info mycluster nfsd-dj3s

# delete 2 nodes from a cluster
> vcd cse node delete mycluster node-dj3s node-dj3s --yes

# list available clusters
> vcd cse cluster list

# info on a given cluster
> vcd cse cluster info

# retrieve cluster config
> vcd cse cluster config mycluster > ~/.kube/config

# check cluster configuration
> kubectl get nodes

# deploy a sample application
> kubectl create namespace sock-shop

> kubectl apply -n sock-shop -f "https://github.com/microservices-demo/microservices-demo/blob/master/deploy/kubernetes/complete-demo.yaml?raw=true"

# check that all pods are running and ready
> kubectl get pods --namespace sock-shop

# access the application
> IP=`vcd cse cluster list|grep '\ mycluster'|cut -f 1 -d ' '`
> open "http://${IP}:30001"

# delete cluster when no longer needed
> vcd cse cluster delete mycluster --yes
```
