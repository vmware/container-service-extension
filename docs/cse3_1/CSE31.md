---
layout: default
title: Introduction
---
# What's new in CSE 3.1?

For greenfield installations, please get started with [CSE introduction](INTRO.html).

<a name="overview"></a>
## 1. Overview
* CSE 3.1, when configured with VCD 10.3, life cycle management of native clusters 
  can be performed using VCD's defined entity API [usage](TBD). 
  
* It is no longer needed to start the CSE server with a particular VCD API 
  version. CSE 3.1 is now capable of accepting incoming requests at any supported 
  VCD API version. Refer to changes in the [configuration file](#cse31-config).
  
* A new version of the template recipe cookbook is introduced. Each template 
  definition in the cookbook has new descriptors, letting CSE server deterministically 
  identify the valid templates it can support. Refer to changes in the [configuration file](#cse31-config)
  
* Kubernetes Cluster UI supports cluster upgrade workflows for both native and vSphere with 
  Tanzu clusters.
  
* CSE-CLI supports below workflows for both native and vSphere with Tanzu clusters.
    - cluster upgrade workflow through `vcd cse cluster apply` command.
    - cluster share workflow through `vcd cse cluster share` command.
    
* Newer versions of native Kubernetes templates are available. Refer to 
  [Template announcements](TEMPLATE_ANNOUNCEMENTS.html)

**Terminology:**
* TKG cluster ~ Tanzu Kubernetes  cluster ~ Tanzu Kubernetes Grid cluster ~ vSphere with Tanzu cluster
* TKGI cluster ~ Ent-PKS cluster ~ Tanzu Kubernetes Grid Integrated Edition cluster
* Defined entities ~ Runtime defined entities ~ RDE ~ Defined Entity Framework
* Native entities: Native defined entities representing Native clusters.
* Tkg entities: Tkg defined entities representing Tkg clusters

![user-ctx](img/cse31-user-ctx.png)

<a name="provider-workflows"></a>
## 2. Provider workflows

<a name="cse31-compatibility-matrix"></a>
### 2.1 Compatibility matrix and relevant features

| CSE Server | CSE CLI | CSE UI | Cloud Director | Ent-PKS with NSX-T | Features offered                                                                                    |
|------------|---------|--------|----------------|--------------------|-----------------------------------------------------------------------------------------------------|
| 3.1        | 3.1     | 3.0*   | 10.3           | 1.7 with 2.5.1     | Native, Tkg, and Ent-PKS Cluster management; Life cycle management of both native and tkg through VCD defined entity API  |
| 3.1        | 3.1     | 2.0*   | 10.2           | 1.7 with 2.5.1     | Native, Tkg, and Ent-PKS Cluster management; Defined entity representation for both native and tkg. |
| 3.1        | 3.1     | 1.0.3  | 10.1, 10.0     | 1.7 with 2.5.1     | Native and Ent-PKS cluster management                                                               |
| NA         | 3.1     | 3.0*   | 10.3           | NA                 | Tkg cluster management only                                                                         |
| NA         | 3.1     | 2.0*   | 10.2           | NA                 | Tkg cluster management only                                                                         |

3.0*, 2.0* -> Kubernetes Clusters UI Plugins 3.0 and 2.0 ship with VCD 10.3 and VCD 10.2 respectively.

| VCD version | Max supported API version |
|-------------|---------------------------|
| 10.3        | 36.0                      |
| 10.2        | 35.0                      |
| 10.1        | 34.0                      |
| 10.0        | 33.0                      |

### 2.2 CSE Server

<a name="cse31-config"></a>
#### 2.2.0 Changes in the configuration file
Refer to the [sample config file](CSE_CONFIG.html)

1. Removal of property `api_version`: Starting CSE 3.1, it is no longer needed to start CSE with a 
   particular VCD API version. As a side effect, CSE 3.1 will not recognize `api_version` 
   property under `vcd` section of the config file. This property can be safely deleted.
   
2. Addition of property `legacy_mode`: This property indicates whether CSE server 
   needs to leverage the latest features like the RDE framework, placement policies of VCD or not.
   * set the `legacy_mode` to true if CSE 3.1 is configured with VCD 10.1. End users 
     will see native clusters as regular vApps with some Kubernetes specific metadata.
   * set the `legacy_mode` to false if CSE 3.1 is configured with VCD >= 10.2. 
     End users will see native clusters as VCD's first class objects in the form of RDEs.
   * Note that CSE 3.1, when configured with VCD>=10.2, will not complain if 
     `legacy_mode` is set to true, but this is not recommended as it prevents CSE 3.1 
     to operate at its full potential.
    
3. Location of new template cookbook `remote_template_cookbook_url`: When 
4. Interrelation between the values of `legacy_mode` and `remote_template_cookbook_url`:

#### 2.2.1 Greenfield installation
When CSE 3.0 is configured with vCD 10.2, CSE installation command
`cse install -c config.yaml` does two additional steps over previous versions. 
Refer to [CSE 3.0 installation](CSE_SERVER_MANAGEMENT.html#cse30-greenfield).

#### 2.2.2 Brownfield upgrade
CSE 3.0 has been architecturally redesigned to leverage the latest features of
Cloud Director like Defined entity framework and placement policies. The new
command `cse upgrade` has been introduced to make the old environment fully
forward compatible with the latest technologies used in CSE 3.0. Any previous
version of CSE can be directly upgraded to CSE 3.0 using `cse upgrade` command;
Refer to [CSE 3.0 upgrade command](CSE_SERVER_MANAGEMENT.html#cse30-upgrade-cmd).

#### 2.2.3 Tenant onboarding
The provider needs to perform below operations to enable Kubernetes cluster
deployments in tenant organizations and tenant virtual data centers.
1. Grant rights to the tenant users. Refer to [CSE 3.0 RBAC](RBAC.html#DEF-RBAC)
for more details.
2. Enable the desired organization virtual datacenter(s) for either Native or
Tkg cluster or Ent-PKS deployments.
    * Tkg clusters → [Publish Kubernetes policy on VDC for Tkg Clusters](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-E9839D4E-3024-445E-9D08-372113CF6FE0.html)
    * Native clusters → [Enable VDC for Native clusters](TEMPLATE_MANAGEMENT.html#restrict_templates).
    * Ent-PKS clusters → [Enable VDC for Ent-PKS clusters](ENT_PKS.html#cse-commands)
3. [Publish Kubernetes Clusters UI Plugin](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html)
to the desired organizations.

### 2.3 Kubernetes Clusters UI Plugin
Starting CSE 3.0 and VCD 10.2, Kubernetes Clusters UI Plugin 2.0 is available
out of the box with VCD 10.2. Provider can publish it to the desired tenants
to offer Kubernetes services. Refer to [publish Kubernetes Clusters UI Plugin](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html)

For VCD < 10.2 versions that inter-operate with CSE 3.0, Kubernetes Clusters UI Plugin 1.0.3 must be installed separately by a Provider and published to the desired tenants.
Refer to [Register CSE UI Plugin 1.0.3](CSE_UI_PLUGIN.html) for more details.

<a name="tenant-workflows"></a>
## 3. Tenant workflows
Tenant users can manage the Kubernetes cluster deployments either through 
CSE CLI or Kubernetes Clusters UI Plugin

### 3.1 CLI for Container Extension
CSE 3.0 introduces below changes in CLI

1. CLI is smart enough to display the most relevant commands and their options 
based on the API version with which the CSE server runs. This intelligence is 
enabled when the user logs into the environment using `vcd login` command. 
For example: `vcd cse cluster apply` is displayed only when CSE server runs at API version 35.0.
2. New command `vcd cse cluster apply <create_cluster.yaml>` has been introduced
 in CSE 3.0. Refer to [cluster apply usage](CLUSTER_MANAGEMENT.html#cse30_cluster_apply) for more details.
3. One can use CLI to deploy Tkg Clusters on VCD 10.2 without the installation 
of CSE server. CLI directly communicates with VCD to manage Tanzu Kubernetes clusters.
4. Node commands are deprecated in CSE 3.0 for VCD 10.2. All of the node 
management (or) resize operations are done through `vcd cse cluster apply` 
command in CSE 3.0 with VCD 10.2. Node commands continue to be operational for 
CSE server with VCD < 10.2.
5. New command is available for NFS deletion: `vcd cse cluster delete-nfs`
6. Separate command group is dedicated for Ent-PKS: `vcd cse pks –help`

### 3.2 Kubernetes Clusters UI Plugin

For VCD 10.2, you must use the [Kubernetes Clusters UI Plugin 2.0](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html
) that comes with VCD to manage the cluster deployments.

If you are working with VCD < 10.2, you must use the [Kubernetes Clusters UI
Plugin 1.0.3](CSE_UI_PLUGIN.html) to manage the cluster deployments.

<a name="faq"></a>
## 4. FAQ
Refer to [Troubleshooting](TROUBLESHOOTING.html) and [Known issues](KNOWN_ISSUES.html) pages.
