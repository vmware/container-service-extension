---
layout: default
title: Enterprise PKS enablement
---

# Enterprise PKS enablement
<a name="overview"></a>
## Overview
CSE 2.0 enables orchestration of K8 cluster deployments on VMware Enterprise PKS. 
At the same time, it maintains the CSE 1.x feature set of Native K8 cluster deployments
 directly on VMware vCloud Director. As a result, the capabilities of CSE 2.0 allow 
 tenants to leverage both K8 Providers, Native and Enterprise PKS, for seamless K8 
 cluster deployments while ensuring clusters' isolation between tenants. 
 It also offers great flexibility to administrators to onboard tenants on K8 Provider(s)
  of their choice, be it Native and/or Enterprise PKS.

![conceptual-view-cse](img/ent-pks/01-conceptual.png)

This page talks in detail about CSE 2.0 architecture with Enterprise PKS, 
the infrastructure set-up, configuration steps, as well as, key command line 
interfaces for K8 deployments.

<a name="architecture"></a>
## Architecture
CSE 2.0 architecture comprises of Enterprise PKS Infrastructure stack, vCloud Director Infrastructure stack, and CSE 2.0 modules. The Enterprise PKS Infrastructure stack is necessary only if there is an intention to leverage it for K8 cluster deployments. The diagram below illustrates a physical view of the complete infrastructure, as well as, its logical mapping in to vCloud Director hierarchy, for ease of understanding. 

Legend:
* Green - Depicts vSphere infrastructure managed by vCloud Director, just as CSE 1.x, without any of Enterprise PKS.
* Blue - Depicts the Enterprise PKS infrastructure stack managed and available for use in vCloud Director for K8 cluster deployments. It also illustrates multi-tenancy for K8 cluster deployments on single Enterprise PKS infrastructure.
* Purple - Depicts a single tenant dedicated Enterprise PKS infrastructure stack managed and available for use in vCloud Director for K8 cluster deployments. It also illustrates the use-case of a tenant leveraging multiple instances of Enterprise PKS infrastructure stack, say, to segregate K8s cluster workloads.
* K8-prov - This label depicts the K8 Provider that is enabled on a given tenant's Organization VDC in vCloud Director.

![provider-setup](img/ent-pks/03-provider-setup-1.png)

<a name="infra-view"></a>
## Infrastructure set-up and configuration 

### Before you begin

1. Ensure fresh installation of Enterprise PKS infrastructure stack. 
Also, ensure there are no prior K8 cluster deployments on this stack.
2. Ensure CSE, vCloud Director infrastructure stack, and Enterprise PKS 
infrastructure stack are all in the same management network, without proxy in between.

### Enterprise PKS on-boarding 

Below timeline diagram depicts infrastructure set-up and tenant
 on-boarding. Cloud-provider has to do below steps before on-boarding tenants.
 1. Set up one or more Enterprise PKS-vSphere-NSX-T instances.
 2. Create [Enterprise PKS service accounts](#faq) per each Enterprise PKS instance.
 2. On-board Enterprise PKS instance(s) in vCD
    * Attach Enterprise PKS' corresponding vSphere in vCD through vCD UI.
    * Create provider-vdc(s) in vCD from underlying resources of newly attached Enterprise PKS' vSphere(s).
    Ensure these pvdc(s) are dedicated for Enterprise PKS K8 deployments only.
 3. Install, configure and start CSE 
    * Follow instructions to install CSE 2.0 beta [here](/container-service-extension/RELEASE_NOTES.html) binaries
    * Use `cse config` command to generate `config.yaml` and `pks.yaml` template files.
    * Configure `config.yaml` with vCD and K8 template details.
    * Configure `pks.yaml` with Enterprise PKS details. This file is necessary only 
    if there is an intention to leverage Enterprise PKS for K8 deployments. 
    * Run `CSE install` command. It prepares NSX-T(s) of Enterprise PKS instances for tenant isolation. 
    Ensure this command is run for on-boarding of new Enterprise PKS instances at later point of time.
    * Start the CSE service. 
    
 <a name="tenant-onboarding"></a>   
### Tenant on-boarding
1. Create ovdc(s) in tenant organization from newly created provider-vdc(s) above via vCD UI.
2. Use these [CSE commands](#cse-commands) to grant K8 deployment rights to chosen tenants and tenant-users. Refer 
[RBAC feature](/container-service-extension/RBAC.html) for more details
3. Use [CSE command](#cse-commands) to enable organiation vdc(s) with a chosen K8-provider (native (or) ent-pks).

Below diagram illustrates a time sequence view of setting up the infrastructure for CSE 2.0,
 followed by the on boarding of tenants. The expected steps are executed by Cloud providers 
 or administrators.

![provider-setup](img/ent-pks/04-provider-setup-2.png)

<a name="communication-view"></a>
## CSE, vCD, Enterprise PKS Component Illustration
Below diagram outlines the communication flow between components for the tenant's 
workflow to create a new K8 cluster.

Legend: 
* The path depicted in pink signifies the workflow of K8 cluster deployments on Native K8 Provider Solution in CSE 2.0.
* The path depicted in blue signifies the workflow of K8 cluster deployments on Enterprise K8 Provider Solution in CSE 2.0.

Refer [tenant-workflow](#tenant-workflow) to understand the below decision 
box in grey color in detail.
![communication-flow](img/ent-pks/02-communication-flow.png)

<a name="tenant-workflow"></a>
## Tenant workflow of create-cluster operation

To understand the creation of new K8 cluster workflow in detail, review below flow chart in its entirety. 
In this illustration, user from  tenant "Pepsi" attempts to create a new K8 cluster
 in organization VDC "ovdc-1", and based on the administrator's enablement for "ovdc-1", 
 the course of action can alter.
![tenant-workflow](img/ent-pks/05-tenant-flow.png)

<a name="cse-commands"></a>
## CSE commands
### Administrator commands to on board a tenant

**Granting rights to Tenants and Users:**

Below steps of granting rights are required only if [RBAC feature](/container-service-extension/RBAC.html) is turned on.

```sh
* vcd right add "{cse}:CSE NATIVE DEPLOY RIGHT" -o tenant1
* vcd right add "{cse}:CSE NATIVE DEPLOY RIGHT" -o tenant2
* vcd right add "{cse}:PKS DEPLOY RIGHT" -o tenant1
```
```sh
* vcd role add-right "Native K8 Author" "{cse}:CSE NATIVE DEPLOY RIGHT"
* vcd role add-right "PKS K8 Author" "{cse}:PKS DEPLOY RIGHT"
* vcd role add-right "Omni K8 Author" "{cse}:CSE NATIVE DEPLOY RIGHT"
* vcd role add-right "Omni K8 Author" "{cse}:PKS DEPLOY RIGHT"
```
```sh
* vcd user create 'native-user' 'password' 'Native K8 Author'
* vcd user create 'pks-user' 'password' 'PKS K8 Author'
* vcd user create 'power-user' 'password' 'Omni K8 Author'
```

**Enabling ovdc(s) for a particular K8-provider:**

```sh
* vcd cse ovdc list
* vcd cse ovdc enable ovdc1 -o tenant1 -k native
* vcd cse ovdc enable ovdc2 -o tenant1 -k ent-pks --pks-plan "gold" --pks-cluster-domain "tenant1.com"
* vcd cse ovdc enable ovdc1 -o tenant2 -k native
```

### Cluster management commands
```sh
* vcd cse cluster list
* vcd cse cluster create
* vcd cse cluster info
* vcd cse cluster resize
* vcd cse cluster delete
```

<a name="known-issues"></a>
## Known issues

* Command `vcd cse node info` on native K8 clusters is broken when 
Enterprise PKS is part of CSE set-up
* Command `vcd cse create cluster` on native ovdc(s) when executed by sys-admin is broken.
* Once `vcd cse cluster resize` is run on Enterprise PKS based clusters, commands 
`vcd cse cluster info` and `vcd cse cluster list` on those resized clusters will begin to display 
incomplete results. This is an issue from Enterprise PKS.

Fixes will be coming soon for the above.

<a name="faq"></a>
## FAQ

* How to create an Enterprise PKS service account?
    * Refer [UAA Client](https://docs.pivotal.io/runtimes/pks/1-3/manage-users.html#uaa-client)
    to grant PKS access to a client.
    * Define your own `client_id` and `client_secret`. The scope should be 
    `uaa.none` and the `authorized_grant_types` should be `client_credentials`
    * Example to create client using UAA CLI: `uaac client add test --name test 
    --scope uaa.none 
    --authorized_grant_types client_credentials 
    --authorities clients.read,clients.write,clients.secret,scim.read,scim.write,pks.clusters.manage`
    * Log in to PKS: `pks login -a https://${PKS_UAA_URL}:9021  -k --client-name test --client-secret xx`
    * Input credentials in pks.yaml 
* Are Enterprise PKS based clusters visible in vCD UI?
    * This functionality is not available yet.
     Enterprise PKS based clusters can only be managed via CSE-CLI as of today.
* Do Enterprise PKS based clusters adhere to their parent organization-vdc compute settings?
    * Yes. Both native and Enterprise PkS clusters' combined usage is accounted towards 
    reaching compute-limits of a given organization-vdc resource-pool.
* Are Enterprise PKS clusters isolated at network layer?
    * Yes. Tenant-1 clusters cannot reach Tenant-2 clusters via Node IP addresses.
* Do Enterprise PKS based clusters adhere to its parent organization-vdc storage limits?
    * This functionality is not available yet. As of today, organization-vdc storage limits apply 
    only for native K8 clusters.
* Can native K8 clusters be deployed in organization-vdc(s) dedicated for Ent-PKS?
    * This functionality is not available yet.
* Can tenant get a dedicated storage for their Enterprise PKS based clusters?
    * This functionality is not available yet.
* Why is response-time of commands slower sometimes?
    * The response times for commands can be slow due to variety of reasons. 
    For example - RBAC feature is known to impose some slowness in the system. 
    Enterprise PKS based K8 cluster deployments have some performance implications. 
    The performance optimizations will be coming in near future
* If there are Extension time out errors while executing commands, how can they be remediated?
    * Increase the vCD extension timeout to a higher value. Refer to "Setting the API Extension Timeout" in [here](/CSE_ADMIN.html)

<a name="compatibility-matrix"></a>
## Compatibility matrix

|CSE      | vCD       |Enterprise PKS| NSX-T | 
|---------|-----------|--------------|-------|
|2.0 Beta | 9.5, 9.7  | 1.4          | 2.3   | 



