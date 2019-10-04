---
layout: default
title: Introduction
---

# Introduction
<a name="overview"></a>
## Overview

Container Service Extension (CSE) is a VMware vCloud Director (vCD)
extension that helps tenants create and work with Kubernetes clusters.

CSE brings _Kubernetes as a Service_ to vCD, by creating customized
VM templates (Kubernetes templates) and enabling tenant users to deploy fully functional
Kubernetes clusters as self-contained vApps.

<a name="cseworkflow"></a>
## How CSE Works

CSE has a server component that installs as a vCD extension. It exposes REST
API endpoint points via vCD. CSE also has a client component that plugs in
``vcd-cli``, communicates with the CSE server via the exposed API endpoints, and
facilitates vCD users to create Kubernetes clusters in vCD. The following
diagram illustrates the interactions between the components.

![cse-workflow](img/cse-workflow.png)

<a name="cseusers"></a>
## CSE User Types

**Cloud administrators** handle setting up vCD, CSE config
file, CSE Server, and Kubernetes templates. Cloud administrators are expected to
posses `sysadmin` privileges and as well as experience in vCD administration.

Once CSE Server is running and Kubernetes templates are available, **tenant
organization administrators and users** can use CSE client (``vcd-cli``)
to handle Kubernetes cluster management. This includes deploying
clusters, adding worker nodes, configuring NFS storage, and the
like.

Tenant users who manage Kubernetes clusters are expected to understand
vCD org administration principles. They should have accounts with privileges
required to create vApps and manage them. Finally, such users should understand
Kubernetes cluster management including setting up user access and
defining persistent volumes.

**Developers and other Kubernetes users** interact with CSE Kubernetes
clusters using ``kubectl`` For these users, Kubernetes clusters
work like any other Kubernetes cluster implementation. No special
knowledge of vCloud Director or CSE administration is required.
Such users do not even need a vCloud Director account.

![cse-overview](img/cse-overview.png)
![cse-roles](img/cse-roles.png)
