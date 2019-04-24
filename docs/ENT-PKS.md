---
layout: default
title: Enterprise-PKS enablement
---

# Enterprise-PKS enablement
<a name="overview"></a>
## Overview
CSE 2.0 begins to orchestrate K8 cluster deployment not only on vCD (native) but 
also on Enterprise-PKS servers.  
* Facilitates co-existence of vCD(native) and PKS clusters with in the same tenant boundaries.
* Enforces tenant isolation among PKS-deployed K8 clusters.
* Provides flexibility for admins to enable/disable a given vdc of tenant with a 
particular K8-provider (native | ent-pks | none).

This page talks in detail about CSE-PKS architecture, infrastructure set-up, 
configuration steps and tenant commands among others.

<a name="architecture"></a>
## Architecture

<a name="conceptual-view"></a>
### Conceptual view
![conceptual-view-cse](img/ent-pks/01-conceptual.png)
<a name="communication-view"></a>

### Communication flow between CSE, VCD and PKS
Below diagram outlines the communication flow between various components involved 
for a create-cluster operation. Communication path in pink color illustrates 
work-flow of native K8 deployments and the path in blue illustrates work-flow of
PKS K8 deployments.
Refer [tenant-workflow](#tenant-workflow) to understand the below decision 
box in grey color in detail.
![communication-flow](img/ent-pks/02-communication-flow.png)

<a name="infra-view"></a>
### Infrastructure set-up and Tenant on-boarding

Below architectural and time-line views depict infrastructure set-up and tenant
 on-boarding. Cloud-provider has to essentially do below steps before 
 users can begin to create PKS-K8-deployments.
 1. Set up one or more PKS-vSphere-NSX-T instances.
 2. On-board PKS instances in vCD by creating corresponding provider-vdc(s).
 3. Install and configure CSE with vCD and PKS details. Start CSE server.
    * "CSE install" command prepares NSX-T(s) of PKS instances for tenant isolation.
 4. Tenant on-boarding 
    * Create ovdc(s) in vCD
    * Grant K8 deployment rights to chosen tenants and tenant-users. Refer 
    [RBAC feature](/RBAC.html) for more details
    * Enable ovdc(s) with a chosen K8-provider (native|ent-pks|none).
 

#### Architectural view
![provider-setup](img/ent-pks/03-provider-setup-1.png)
#### Time-line view
![provider-setup](img/ent-pks/04-provider-setup-2.png)

<a name="tenant-workflow"></a>
### Tenant workflow of create-cluster operation
![tenant-workflow](img/ent-pks/05-tenant-flow.png)

<a name="persona based workflows"></a>
## Persona based commands
### Cloud-provider
#### Tenant on-boarding

##### Granting rights to Tenants and Users

* vcd right add "{cse}:CSE NATIVE DEPLOY RIGHT" -o tenant1
* vcd right add "{cse}:CSE NATIVE DEPLOY RIGHT" -o tenant2
* vcd right add "{cse}:PKS DEPLOY RIGHT" -o tenant1

* vcd role add-right "Native K8 Author" "{cse}:CSE NATIVE DEPLOY RIGHT"
* vcd role add-right "PKS K8 Author" "{cse}:PKS DEPLOY RIGHT"
* vcd role add-right "Omni K8 Author" "{cse}:CSE NATIVE DEPLOY RIGHT"
* vcd role add-right "Omni K8 Author" "{cse}:PKS DEPLOY RIGHT"

* vcd user create 'native-user' 'password' 'Native K8 Author'
* vcd user create 'pks-user' 'password' 'PKS K8 Author'
* vcd user create 'power-user' 'password' 'Omni K8 Author'

##### Enabling ovdc(s) for a particular K8-provider

* vcd cse ovdc list
* vcd cse ovdc enable ovdc1 -o tenant1 -k native
* vcd cse ovdc enable ovdc2 -o tenant1 -k ent-pks --pks-plan "gold" --pks-cluster-domain "tenant1.com"
* vcd cse ovdc enable ovdc1 -o tenant2 -k native

### Tenant/Admin operations
* vcd cse cluster list
* vcd cse cluster create
* vcd cse cluster info
* vcd cse cluster resize
* vcd cse cluster delete

<a name="assumptions"></a>
## Assumptions
* Fresh Ent-PKS (vSphere & NSX-T) setup. PKS instances should not have any prior K8 deployments.
* CSE, vCD and Ent-PKS instances in the same management network.
* PKS service accounts with minimum required privileges for CRUD on clusters.

<a name="recommendations"></a>
## Recommendations
* Dedicated provider-vdc(s) for PKS K8 deployments.
* Dedicated org-vdc(s) for PKS K8 deployments.

<a name="known issues"></a>
## Known issues

<a name="faq"></a>
## FAQ
