---
layout: default
title: Introduction
---
# What's new in CSE 3.0?

For greenfield installations, please get started with [CSE introduction](INTRO.html).
<a name="overview"></a>
## 1. Overview
* CLI for Container Extension and Kubernetes Cluster UI Plugin can be used to 
manage Cloud Director provisioned [Tanzu Kubernetes Clusters](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-E9839D4E-3024-445E-9D08-372113CF6FE0.html)
 alongside Native and TKGI (Ent-PKS) clusters.
 
* Native clusters are now represented as defined entities. CSE 3.0 has been 
architecturally redesigned to leverage the latest features of Cloud Director 
(>=10.2) like the [Defined entity framework](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-0749DEA0-08A2-4F32-BDD7-D16869578F96.html), 
and placement policies. Users will not see any difference in the functionality 
of native clusters, but the underlying implementation has been enhanced to 
leverage defined entities for persisting native cluster entities in vCD DB and 
placement policies for [restricting native  deployments](TEMPLATE_MANAGEMENT.html#restrict_templates) 
to specific organization virtual datcenters (ovdcs). Users can now query native 
clusters using vCD's defined entity API. 

* Separate command group for TKGI (Ent-PKS).

**Terminology:**
* TKG cluster ~ Tanzu Kubernetes  cluster ~ Tanzu Kubernetes Grid cluster ~ vSphere with Tanzu cluster
* TKGI cluster ~ Ent-PKS cluster ~ Tanzu Kubernetes Grid Integrated Edition cluster
* Defined entities ~ Runtime defined entities ~ RDE ~ Defined Entity Framework
* Native entities: Native defined entities representing Native clusters.
* Tkg entities: Tkg defined entities representing Tkg clusters

![user-ctx](img/cse30-user-ctx.png)
![system-ctx](img/cse30-system-ctx.png)

<a name="provider-workflows"></a>
## 2. Provider workflows

<a name="cse30-compatibility-matrix"></a>
### 2.1 Compatibility matrix and relevant features

| CSE CLI | CSE UI | CSE Server | Cloud Director | Ent-PKS | Features offered                                                                                    |
|---------|--------|------------|----------------|---------|-----------------------------------------------------------------------------------------------------|
| 3.0     | 2.0    | NA         | 10.2           | NA      | Tkg cluster management only                                                                         |
| 3.0     | 2.0    | 3.0        | 10.2           | ?       | Native, Tkg, and Ent-PKS Cluster management; Defined entity representation for both native and tkg. |
| 3.0     | 1.0.3  | 3.0        | 10.1, 10.0     | ?       | Legacy features (Native and Ent-PKS cluster management)                                             |

### 2.2 CSE Server
#### 2.2.1 Greenfield installation
With CSE 3.0 - vCD 10.2 combination, CSE installation command 
`cse install -c config.yaml` does two additional steps than what it used to do 
in the earlier versions. Refer [CSE 3.0 installation](CSE_SERVER_MANAGEMENT.html#cse30-greenfield).

#### 2.2.2 Brownfield upgrade
CSE 3.0 has been architecturally redesigned to leverage the latest features of 
Cloud Director like Defined entity framework and placement policies. The new 
command `cse upgrade` has been introduced to make the old environment fully 
forward compatible with the latest technologies used in CSE 3.0. Any previous 
version of CSE can be directly upgraded to CSE 3.0 using `cse upgrade` command; 
Refer [CSE 3.0 upgrade command](CSE_SERVER_MANAGEMENT.html#cse30-upgrade-cmd).

#### 2.2.3 Tenant onboarding
The provider needs to perform below operations to enable Kubernetes cluster 
deployments in tenant organizations and tenant virtual data centers.
1. Grant rights to the tenant users. Refer [CSE 3.0 RBAC](RBAC.html#DEF-RBAC) for more details.
2. Enable the desired organization virtual datacenter(s) for either Native or Tkg cluster deployments.
    * Tkg clusters → [Publish Kubernetes policy for Tkg Clusters](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-E9839D4E-3024-445E-9D08-372113CF6FE0.html)
    * Native clusters → [Publish Native placement policy on ovdc](TEMPLATE_MANAGEMENT.html#restrict_templates). 
    In other words, run `vdc cse ovdc enable <vdc-name>` command.
3. Publish Kubernetes Clusters UI plugin to the desired organizations.

### 2.3 Kubernetes Clusters UI plug-in
To be filled by Andrew. UI plug-in is now part of vCD and the provider can 
publish UI plug-in to the desired tenants.

## 3. Tenant workflows
Tenant users can manage the Kubernetes cluster deployments either through CSE CLI or Kubernetes clusters UI plug-in

### 3.1 CLI for Container Extension
1. New command `vcd cse cluster apply <create_cluster.yaml>` has been introduced
 in CSE 3.0. Refer [cluster apply usage](CLUSTER_MANAGEMENT.html#cse30_cluster_apply) for more details.
2. [Other miscellaneous changes in CLI 3.0](CLUSTER_MANAGEMENT.html#cse30_cli_changes)

### 3.2 Kubernetes Clusters UI plug-in
1. [Deploy Tanzu Kubernetes Cluster](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Tenant-Portal-Guide/GUID-CA4A2F24-3E7C-4992-9E54-61AB8A4B80E7.html)
2. [Deploy Native cluster](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Tenant-Portal-Guide/GUID-F831C6A1-8280-4376-A6D9-9D997D987E91.html)
3. [Deploy TKGI (Ent-PKS) cluster](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Tenant-Portal-Guide/GUID-1BDF9D95-1484-4C9D-8748-26C8FC773530.html)

<a name="faq"></a>
## 4. FAQ
Refer [Troubleshooting](TROUBLESHOOTING.html) and [Known issues](KNOWN_ISSUES.html) pages.
