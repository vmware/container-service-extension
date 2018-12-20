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
go through to install `vcd cse` and creat a cluster.  It includes 
some internals of CSE so that you can understand what is happening 
behind the covers. 

![cse-usage](img/cse-usage-2.png)

CSE Kubernetes clusters can include persistent volumes mounted on NFS. 
Procedures for creating and managing NFS nodes are located on the 
[NFS Node Management](/NFS_STATIC_PV.html) page. 

<a name="usefulcommands"></a>
## Useful Commands
`vcd cse ...` commands are used by tenant/org administrators and users to:
- list templates
- get CSE Server status
- create, list, and delete clusters/nodes

Here is a summary of commands available to manage templates, clusters
and nodes:

| Command                                           | Description                                     |
|:--------------------------------------------------|:--------------------------------------------|
| `vcd cse template list`                           | List available templates to create clusters |
| `vcd cse cluster create CLUSTER_NAME`           | Create a new Kubernetes cluster             |
| `vcd cse cluster create CLUSTER_NAME --enable-nfs`| Create a new Kubernetes cluster with NFS PV support.|
| `vcd cse cluster list`                            | List created clusters.                      |
| `vcd cse cluster delete CLUSTER_NAME`           | Delete a Kubernetes cluster.                |
| `vcd cse node create CLUSTER_NAME --nodes n`    | Add `n` nodes to a cluster.                 |
| `vcd cse node create CLUSTER_NAME --type nfsd`  | Add an NFS node to a cluster.               |
| `vcd cse node list CLUSTER_NAME`                | List nodes of a cluster.                    |
| `vcd cse node delete CLUSTER_NAME NODE_NAME` | Delete nodes from a cluster.                |

By default, CSE Client will display the task progress until the
task finishes or fails. The `--no-wait` will return the task
information, which you can use to monitor the task progress:

```sh
> vcd --no-wait cse cluster create CLUSTER_NAME --network intranet --ssh-key ~/.ssh/id_rsa.pub

# displays the status and progress of the task
> vcd task wait 377e802d-f278-44e8-9282-7ab822017cbd

# lists the current running tasks in the organization
> vcd task list running
```

<a name="automation"></a>
## Automation
`vcd cse` commands can be scripted to automate the creation and operation
of Kubernetes clusters and nodes.

Users can also interact with CSE via the Python package or the CSE
API exposed in vCD.

This Python script creates a Kubernetes cluster on vCloud Director:
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

# add 2 worker nodes to a cluster with 4GB of ram and 4 CPUs each, from the photon-v2 template
# and using the specified storage profile
> vcd cse node create mycluster --nodes 2 --network intranet --ssh-key ~/.ssh/id_rsa.pub --memory 4096 --cpu 4 --template photon-v2 --storage-profile Development

# add 1 nfsd node to a cluster with 4GB of ram and 4 CPUs each, from the photon-v2 template
# and using the specified storage profile
> vcd cse node create mycluster --nodes 1 --type nfsd --network intranet --ssh-key ~/.ssh/id_rsa.pub --memory 4096 --cpu 4 --template photon-v2 --storage-profile Development

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

