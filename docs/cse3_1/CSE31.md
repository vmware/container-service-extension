---
layout: default
title: Introduction
---
# What's new in CSE 3.1?

For greenfield installations, please get started with [CSE introduction](INTRO.html).

<a name="overview"></a>
## 1. Overview

**Terminology:**
* TKG cluster : Clusters deployed by CSE using VMware Tanzu Kubernetes Grid OVA.
* Native cluster : Clusters deployed by CSE using upstream Kubernetes.
* TKG-S cluster : VMware Tanzu Kubernetes Grid Service cluster a.k.a vSphere with Tanzu cluster.
* TKG-I cluster : Enterprise PKS cluster a.k.a VMware Tanzu Kubernetes Grid Integrated Edition cluster.
* Defined entities : Runtime defined entities a.k.a RDE or Defined Entity Framework.
* Native entities: Runtime defined entities representing Native clusters.
* TKG-S entities: Runtime defined entities representing TKG-S clusters.
* Defined entity API: VCD's generic defined entity api to manage lifecycle of RDEs.
* UI plugin : Kubernetes Container Clusters UI plugin, that is used to manage Native, TKG, TKG-S, TKG-I clusters from VCD UI.

### CSE 3.1.2

* Kubernetes Container Cluster API for VCD. Learn more about [CAPI for VCD](link to do)
* Kubernetes External Cloud Provider for VCD updated to v1.1.0. Learn more about [CPI for VCD](https://github.com/vmware/cloud-provider-for-cloud-director/blob/1.1.0/README.md)
* Kubernetes Container Storage Interface for VCD updated to v1.1.0. Learn more about [CSI for VCD](https://github.com/vmware/cloud-director-named-disk-csi-driver/blob/1.1.0/README.md)
* Kubernetes Container Clusters plugin is updated to version 3.2.0. The plugin ships with VCD 10.3.2.
* Support for injecting proxy information into TKG clusters. Learn more about the feature, [here](CSE_CONFIG.html#extra_options).
* New command option to Force Delete clusters that have failed to deploy and are in unremovable state. Learn more, [here](CLUSTER_MANAGEMENT.html#force_delete).

### CSE 3.1.1

* Support for importing VMware Tanzu Kubernetes Grid OVAs and deploying Kubernetes clusters.
  * Learn more about using [VMware Tanzu Kubernetes Grid OVAs with CSE](TEMPLATE_MANAGEMENT.html#tkgm_templates)
  * Learn more about deploying a Kubernetes cluster based on VMware Tanzu Kubernetes Grid [here](CLUSTER_MANAGEMENT.html#tkgm_clusters)
  * Antrea as CNI
* Kubernetes External Cloud Provider for VCD. Learn more about [CPI for VCD](https://github.com/vmware/cloud-provider-for-cloud-director/blob/1.0.0/README.md)
* Kubernetes Container Storage Interface for VCD. Learn more about [CSI for VCD](https://github.com/vmware/cloud-director-named-disk-csi-driver/blob/1.0.0/README.md)
* Kubernetes Container Clusters plugin is updated to version 3.1.0, which includes support for Tanzu Kubernetes Grid. The plugin ships with VCD 10.3.1.
* Deploy externally accessible TKG clusters on NSX-T based Routed OrgVDC Networks from Kubernetes Container Clusters UI plugin v3.1.0.
* **Deprecation of Photon OS 2.0 based native templates**, they will be removed in a future CSE release.

### CSE 3.1.0

* CSE 3.1 need not be started with a particular VCD API version. It is now capable of
  accepting incoming requests at any supported VCD API version. Refer to changes in the [configuration file](#cse31-config).
* A new version of the template recipe cookbook 2.0.0 is introduced. Each template has
  a new descriptor that lets CSE 3.1 determine the templates it can support.
  Refer to changes in the [configuration file](#cse31-config)
* CSE CLI offers new capabilities to upgrade and share clusters. Refer to the [commands](CLUSTER_MANAGEMENT.html#cse31_cluster_apply) here.
* Kubernetes Container Clusters UI Plugin 3.0 offers a new capability to upgrade clusters.
  It also enables one to view clusters that are deployed across multisite VCD instances.
* Newer versions of native Kubernetes templates are available. Refer to
  [Template announcements](TEMPLATE_ANNOUNCEMENTS.html)
* CSE 3.1 drops the support with VCD 10.0.
* **Deprecation of TKG-I (Enterprise PKS)** - CSE Server and Kubernetes Container Clusters plugin will soon drop support for TKG-I. Consider using VMware Tanzu Kubernetes Grid (TKG) or VMware Tanzu Kubernetes Grid Service (TKG-S) for management of Kubernetes clusters with VCD.

## User Context Diagram

![user-ctx](img/cse31-user-ctx.png)

<a name="provider-workflows"></a>
## 2. Provider workflows

<a name="cse31-compatibility-matrix"></a>
### 2.1 Compatibility matrix and relevant features

**Kubernetes Container Clusters UI plugin compatibility matrix**

| CSE Server/CLI | UI plugin | Cloud Director | Comments               |
|----------------|-----------|----------------|------------------------|
| 3.1.2          | 3.2.0     | 10.3.2         | Plugin ships with VCD  |
| 3.1.2          | 3.1.0     | 10.3.1         | Plugin ships with VCD  |
| 3.1.2          | 2.2.0     | 10.2.2         | Plugin ships with VCD  |
| 3.1.2          | 1.0.3     | 10.1           | Download from [here](https://github.com/vmware/container-service-extension/raw/master/cse_ui/1.0.3/container-ui-plugin.zip) |
| 3.1.1          | 3.1.0     | 10.3.1         | Plugin ships with VCD  |
| 3.1.1          | 2.2.0     | 10.2.2         | Plugin ships with VCD  |
| 3.1.1          | 1.0.3     | 10.1           | Download from [here](https://github.com/vmware/container-service-extension/raw/master/cse_ui/1.0.3/container-ui-plugin.zip) |
| 3.1.0          | 3.0.0     | 10.3.0         | Plugin ships with VCD  |
| 3.1.0          | 2.0.0     | 10.2.0         | Plugin ships with VCD  |
| 3.1.0          | 1.0.3     | 10.1           | Download from [here](https://github.com/vmware/container-service-extension/raw/master/cse_ui/1.0.3/container-ui-plugin.zip) |


**Native cluster comaptiblity matrix**

| CSE Server/CLI | Cloud Director | NSX-T | NSX-V   | Comments                            |
|----------------|----------------|-------|---------|-------------------------------------|
| 3.1.2          | 10.3.2         | 3.1.1 | 6.4.10† | Cluster representation as RDE 2.0.0 |
| 3.1.2          | 10.3.1         | 3.1.1 | 6.4.10† | Cluster representation as RDE 2.0.0 |
| 3.1.2          | 10.2.2         | 3.1.1 | 6.4.10† | Cluster representation as RDE 1.0.0 |
| 3.1.2          | 10.1           | n/a   | 6.4.8†  | Cluster representation as vApp      |
| 3.1.1          | 10.3.1         | 3.1.1 | 6.4.10† | Cluster representation as RDE 2.0.0 |
| 3.1.1          | 10.2.2         | 3.1.1 | 6.4.10† | Cluster representation as RDE 1.0.0 |
| 3.1.1          | 10.1           | n/a   | 6.4.8†  | Cluster representation as vApp      |
| 3.1.0          | 10.3.0         | 3.1.1 | 6.4.10† | Cluster representation as RDE 2.0.0 |
| 3.1.0          | 10.2.0         | 3.1.1 | 6.4.10† | Cluster representation as RDE 1.0.0 |
| 3.1.0          | 10.1           | n/a   | 6.4.8†  | Cluster representation as vApp      |

<sub><sup>† - With NSX-V, CSE doesn't support creation of clusters on routed Org VDC networks.</sup></sub>

**TKG compatibility matrix**

| CSE Server/CLI   | Cloud Director | NSX-T with Avi             |
|------------------|----------------|----------------------------|
| 3.1.2            | 10.3.2         | NSX-T 3.1.3 and Avi 21.1.1 |
| 3.1.2            | 10.3.1         | NSX-T 3.1.3 and Avi 21.1.1 |
| 3.1.1            | 10.3.1         | NSX-T 3.1.3 and Avi 21.1.1 |

**Note**: Ubuntu 20.04 Kubernetes OVAs from VMware Tanzu Kubernetes Grid Versions 1.4.0, 1.3.1, 1.3.0 are supported.

**TKG-S compatibility matrix**

| CSE CLI | UI plugin  | Cloud Director |
|---------|------------|----------------|
| 3.1.2   | 3.2.0      | 10.3.2         |
| 3.1.2   | 3.1.0      | 10.3.1         |
| 3.1.2   | 2.2.0      | 10.2.2         |
| 3.1.1   | 3.1.0      | 10.3.1         |
| 3.1.1   | 2.2.0      | 10.2.2         |
| 3.1.0   | 3.0.0      | 10.3.0         |
| 3.1.0   | 2.0.0      | 10.2.0         |

**Note** : TKG-S cluster management doesn't need CSE server to be running.

**TKG-I compatibility matrix**

| CSE Server          | Cloud Director       | Ent-PKS | NSX-T |
|---------------------|----------------------|---------|-------|
| 3.1.2, 3.1.1, 3.1.0 | 10.3.1, 10.2.2, 10.1 | 1.7     | 2.5.1 |

### 2.2 CSE Server

<a name="cse31-config"></a>
#### 2.2.1 Changes in the configuration file
Refer to the [sample config file](CSE_CONFIG.html)

### CSE 3.1.2
1. Addition of new [extra_options](CSE_CONFIG.html#extra_options) section that allows
Providers to specify proxy details for TKG clusters.

### CSE 3.1.1

1. Addition of property [no_vc_communication_mode](CSE_CONFIG.html#no_vc_communication_mode) under `service` section.
2. `vcs` section is no longer required if `no_vc_communication_mode` is set to True.
3. Removal of properties `default_template_name` and `default_template_revision` from `broker` section.

### CSE 3.1.0

1. Removal of property [api_version](CSE_CONFIG.html#api_version)
2. Addition of property [legacy_mode](CSE_CONFIG.html#legacy_mode)
3. [New template cookbook 2.0](CSE_CONFIG.md#template_cookbook_20) is introduced;
   refer to the  `remote_template_cookbook_url` for the location
4. [mqtt](CSE_CONFIG.html#mqtt_section) property must be enabled when CSE 3.1 is configured with VCD 10.3.

#### 2.2.2 Greenfield installation

Refer to [CSE 3.1 installation](CSE_SERVER_MANAGEMENT.html#cse31-greenfield).

<a name="brown_field_upgrades"></a>
#### 2.2.3 Brownfield upgrade

**3.1.2**  
CSE can be upgraded from version 3.1.1, 3.1.0 and 3.0.z to version 3.1.2 GA.
Any CSE release older than CSE 3.0.0 first needs to be upgraded to
CSE 3.0.z product line before it can be upgraded to CSE 3.1.2.

<a name="remove_tkgm"></a>
**Note** :
If Tanzu Kubernetes Grid (TKG) distribution is enabled
on [CSE 3.0.z](https://github.com/vmware/container-service-extension-templates/blob/tkgm/TKG_INSTRUCTIONS.md),
then the steps mentioned below must be followed in order to upgrade to CSE 3.1.2.

1. Evaluate your environment for any stateful applications that run on TKG clusters
powered by CSE 3.0.z. If you wish to retain these application's data, then leverage
a Kubernetes application backup/restore strategy to backup the applications data so you can restore it later.
2. The next set of steps lead you through removal of TKG clusters from CSE 3.0.z after which you can safely upgrade to CSE 3.1.2  
  2.1. Delete all deployed TKG clusters across all tenants via `vcd-cli` or `Kubernetes Container Clusters UI plugin`.  
  2.2. Disable TKG deployment on all Org VDCs via `vcd cse ovdc disable`.  
  2.3. Stop the CSE server.  
  2.4. Delete all TKG templates via VCD UI.  
  2.5. Remove the VM Placement Policy `cse---tkgm` from the system via VCD UI or VCD REST api.  
  2.6. Revert CSE configuration file to disable TKG.  
3. Upgrade CSE via `cse upgrade` command.
4. Create new TKG clusters from Ubuntu 20.04 TKG OVAs, using CSE 3.1.2.
5. Restore applications on newly created TKG clusters.

Refer to [CSE 3.1 upgrade command](CSE_SERVER_MANAGEMENT.html#cse31-upgrade-cmd) for details.


**3.1.1**  
CSE can be upgraded from CSE 3.1.0 and CSE 3.0.z to 3.1.1 GA.
Any CSE release older than CSE 3.0.0 first needs to be upgraded to
CSE 3.0.z product line before it can be upgraded to CSE 3.1.1.

<a name="remove_tkgm_311"></a>
**Note** :
If Tanzu Kubernetes Grid (TKG) distribution is enabled
on [CSE 3.0.z](https://github.com/vmware/container-service-extension-templates/blob/tkgm/TKG_INSTRUCTIONS.md),
then please consider upgrading to CSE 3.1.1 following these [steps](CSE31.html#remove_tkgm).

Refer to [CSE 3.1 upgrade command](CSE_SERVER_MANAGEMENT.html#cse31-upgrade-cmd) for details.

**3.1.0**
CSE can be upgraded to 3.1.0, only from CSE 3.0.z product line.
Any CSE release older than CSE 3.0.0 first needs to be upgraded to
CSE 3.0.z product line before it can be upgraded to CSE 3.1.0.

<a name="remove_tkgm_310"></a>
**Note** :
If Tanzu Kubernetes Grid (TKG) distribution is enabled
on [CSE 3.0.z](https://github.com/vmware/container-service-extension-templates/blob/tkgm/TKG_INSTRUCTIONS.md),
then please consider upgrading to CSE 3.1.1 following these [steps](CSE31.html#remove_tkgm).

Refer to [CSE 3.1 upgrade command](CSE_SERVER_MANAGEMENT.html#cse31-upgrade-cmd) for details.

#### 2.2.4 Tenant onboarding
The provider needs to perform below operations to enable Kubernetes cluster
deployments in tenant organizations and tenant virtual data centers.
1. Grant rights to the tenant users. Refer to [CSE 3.1 RBAC](RBAC.html#rde_rbac)
for more details.
2. Enable the desired organization virtual datacenter(s) for Native, TKG-S, and/or TKG-I deployments.
    * Native clusters → [Enable VDC for Native clusters](TEMPLATE_MANAGEMENT.html#restrict_templates).
    * TKG-S clusters → [Publish Kubernetes policy on VDC for TKG-S Clusters](https://docs.vmware.com/en/VMware-Cloud-Director/10.3/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-E9839D4E-3024-445E-9D08-372113CF6FE0.html)
    * TKG-I clusters → [Enable VDC for TKG-I clusters](ENT_PKS.html#cse-commands)
3. [Publish Kubernetes Container Clusters UI plugin](https://docs.vmware.com/en/VMware-Cloud-Director/10.3/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html)
to the desired organizations.

### 2.3 Kubernetes Container Clusters UI plugin
Kubernetes Container Clusters UI plugin 3.2.0 is available out of the box with VCD 10.3.2.  
Kubernetes Container Clusters UI plugin 3.1.0 is available out of the box with VCD 10.3.1.  
Kubernetes Container Clusters UI plugin 3.0.0 is available out of the box with VCD 10.3.0.

Provider can publish it to the desired tenants to offer Kubernetes services.
Refer to [publish Kubernetes Container Clusters UI plugin](https://docs.vmware.com/en/VMware-Cloud-Director/10.3/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html).
For VCD 10.2.z that inter-operates with CSE 3.1.z, Provider must use the
Kubernetes Container Clusters UI plugin 2.y.z that comes with VCD to offer Kubernetes Services.
For VCD versions prior to 10.2 that inter-operate with CSE 3.1.z,
Kubernetes Container Clusters UI plugin 1.0.3 must be installed separately by Provider and
published to the desired tenants. Refer to [Register CSE UI plugin 1.0.3](CSE_UI_PLUGIN.html)
for more details.

<a name="tenant-workflows"></a>
## 3. Tenant workflows
Tenant users can manage the Kubernetes cluster deployments either through
CSE CLI or Kubernetes Container Clusters UI plugin

### 3.1 CLI for Container Extension
CSE 3.1.0 introduces below changes in CLI

1. Cluster upgrades (Native and vSphere with Tanzu) can now be performed using `vcd cse cluster apply <upgrade_cluster.yaml>`.
   Refer to [cluster apply usage](CLUSTER_MANAGEMENT.html#cse31_cluster_apply) for more details.
2. Clusters can be shared to other users using new `vcd cse cluster share` command.
   Refer to [cluster share usage](CLUSTER_MANAGEMENT.html#cse31_cluster_share)

### 3.2 Kubernetes Container Clusters UI plugin
For VCD 10.3.z, you must use the [Kubernetes Container Clusters UI plugin 3.y.0](https://docs.vmware.com/en/VMware-Cloud-Director/10.3/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html) that comes with VCD to manage the cluster deployments.
For VCD 10.2.z, you must use the [Kubernetes Container Clusters UI plugin 2.y.0](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html) that comes with VCD to manage the cluster deployments.

If you are working with VCD versions prior to 10.2, you must use the [Kubernetes Container Clusters UI plugin 1.0.3](CSE_UI_PLUGIN.html) to manage the cluster deployments.

<a name="faq"></a>
## 4. FAQ
Refer to [Troubleshooting](TROUBLESHOOTING.html) and [Known issues](KNOWN_ISSUES.html) pages.
