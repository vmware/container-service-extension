---
layout: default
title: Introduction
---
# What's new in CSE 3.1?

For greenfield installations, please get started with [CSE introduction](INTRO.html).

<a name="overview"></a>
## 1. Overview
* CSE 3.1, when configured with VCD 10.3, life cycle management of native clusters 
  can be performed using VCD's defined entity API. Refer to the [API usage](CLUSTER_MANAGEMENT_RDE.html) for details.
  
* It is no longer needed to start the CSE server with a particular VCD API 
  version. CSE 3.1 is now capable of accepting incoming requests at any supported 
  VCD API version. Refer to changes in the [configuration file](#cse31-config).
  
* A new version of the template recipe cookbook is introduced. Each template 
  definition in the cookbook has new descriptors, letting CSE server deterministically 
  identify the valid templates it can support. Refer to changes in the [configuration file](#cse31-config)
  
* Kubernetes Cluster UI supports cluster upgrade workflows for both native and vSphere with 
  Tanzu clusters.
  
* CSE-CLI supports below workflows for both native and vSphere with Tanzu clusters.
    - cluster upgrades are available using `vcd cse cluster apply` command.
    - cluster sharing with other users is available using `vcd cse cluster share` command.
    
* Newer versions of native Kubernetes templates are available. Refer to 
  [Template announcements](TEMPLATE_ANNOUNCEMENTS.html)

**Terminology:**
* TKG-S cluster ~ Tanzu Kubernetes cluster ~ Tanzu Kubernetes Grid cluster ~ vSphere with Tanzu cluster
* TKGI cluster ~ Ent-PKS cluster ~ Tanzu Kubernetes Grid Integrated Edition cluster
* Defined entities ~ Runtime defined entities ~ RDE ~ Defined Entity Framework
* Native entities: Native defined entities representing Native clusters.
* Tkg entities: Tkg defined entities representing Tkg clusters
* Defined entity API: VCD's generic defined entity api to life cycle manage RDEs.

![user-ctx](img/cse31-user-ctx.png)

<a name="provider-workflows"></a>
## 2. Provider workflows

<a name="cse31-compatibility-matrix"></a>
### 2.1 Compatibility matrix and relevant features

| CSE Server | CSE CLI | CSE UI | Cloud Director | Ent-PKS with NSX-T | Features offered                                                                                    |
|------------|---------|--------|----------------|--------------------|-----------------------------------------------------------------------------------------------------|
| 3.1        | 3.1     | 3.0*   | 10.3           | 1.7 with 2.5.1     | Native, TKG-S, and Ent-PKS Cluster management; Life cycle management of both native through VCD defined entity API  |
| 3.1        | 3.1     | 2.0*   | 10.2           | 1.7 with 2.5.1     | Native, TKG-S, and Ent-PKS Cluster management; Defined entity representation for both native and tkg. |
| 3.1        | 3.1     | 1.0.3  | 10.1           | 1.7 with 2.5.1     | Native and Ent-PKS cluster management                                                               |
| NA         | 3.1     | 3.0*   | 10.3           | NA                 | TKG-S cluster management only                                                                         |
| NA         | 3.1     | 2.0*   | 10.2           | NA                 | TKG-S cluster management only                                                                         |

3.0*, 2.0* -> Kubernetes Clusters UI Plugins 3.0 and 2.0 ship with VCD 10.3 and VCD 10.2 respectively.

| VCD version | Max supported API version |
|-------------|---------------------------|
| 10.3        | 36.0                      |
| 10.2        | 35.0                      |
| 10.1        | 34.0                      |

### 2.2 CSE Server

<a name="cse31-config"></a>
#### 2.2.0 Changes in the configuration file
Refer to the [sample config file](CSE_CONFIG.html)

1. Removal of property `api_version`: Starting CSE 3.1, it is no longer needed to start CSE with a 
   particular VCD API version. As a side effect, CSE 3.1 will not recognize `api_version` 
   property under `vcd` section of the config file. This property can be safely deleted 
   from the existing configuration files.
   
2. Addition of property `legacy_mode`: This property indicates whether CSE server 
   needs to leverage the latest features of VCD like RDE framework, placement policies or not.
   * set the `legacy_mode` to true if CSE 3.1 is configured with VCD 10.1. End users 
     will see native clusters as regular vApps with some Kubernetes specific metadata.
   * set the `legacy_mode` to false if CSE 3.1 is configured with VCD >= 10.2. 
     End users will see native clusters as VCD's first class objects in the form of RDEs.
   * Note that CSE 3.1, when configured with VCD>=10.2, will not complain if 
     `legacy_mode` is set to true, but this is not recommended as it prevents CSE 3.1 
     to operate at its full potential.
    
3. New template cookbook `remote_template_cookbook_url`: CSE 3.1 config must refer
   to http://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template_v2.yaml
   Note that CSE <= 3.0 will not work with the new template cookbook.
   - When `legacy_mode` is set to true, `remote_template_cookbook_url` must refer to old template cookbook 
     https://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template.yaml
     
4. For CSE 3.1 to work with VCD 10.3, it is a mandatory step to enable `mqtt` property. 
   AMQP configuration is not supported for the combination of CSE 3.1 and VCD 10.3.

#### 2.2.1 Greenfield installation 
Refer to [CSE 3.1 installation](CSE_SERVER_MANAGEMENT.html#cse31-greenfield).

#### 2.2.2 Brownfield upgrade

CSE 3.1 can only be upgraded from 3.0.X.
Below are the few valid upgrade paths and the resultant changes in the environment.

An example on reading below upgrade paths - `CSE 3.0.X, VCD 10.2 (api_version=34.0) -> CSE 3.1, VCD 10.2 (legacy_mode=true)`:
Environment with CSE 3.0.X, configured with VCD 10.2, running at the specified api_version=34.0 (config.yaml) 
can be upgraded to environment CSE 3.1, configured with VCD 10.2, running with `legacy_mode` set to true.

1. CSE 3.0.X, VCD 10.1 (api_version=34.0) -> CSE 3.1, VCD 10.1 (legacy_mode=true)
   - Native clusters will remain regular vApps with Kubernetes specific metadata.
   - Existing templates in the environment will continue to work.
2. CSE 3.0.X, VCD 10.2 (api_version=34.0) -> CSE 3.1, VCD 10.2 (legacy_mode=false)
   - Native clusters will have a new representation in the form of 
     RDE `urn:vcloud:type:cse:nativeCluster:1.0.0` entities.
   - Existing templates will no longer be recognized by CSE 3.1. 
   - It is strongly recommended to force recreate the templates from the new template cookbook. 
     CSE server needs at least one valid template in order to start.
   - Existing clusters must be upgraded to newer templates in order to enable operations like resize.
3. CSE 3.0.X, VCD 10.2 (api_version=34.0) -> CSE 3.1, VCD 10.3 (legacy_mode=false)
   - Native clusters will have a new representation  in the form of 
     RDE `urn:vcloud:type:cse:nativeCluster:2.0.0` entities.
   - Existing templates will no longer be recognized by CSE 3.1. 
   - It is strongly recommended to force create the templates from the new template cookbook. 
     CSE server needs at least one valid template in order to start.
   - Existing clusters must be upgraded to newer templates in order to enable operations like resize.
   - VCD's defined entity api can be used to initiate CRUD operations on the clusters.
4. CSE 3.0.X, VCD 10.2 (api_version=35.0) -> CSE 3.1, VCD 10.3 (legacy_mode=false)
   - Native clusters will be upgraded from `urn:vcloud:type:cse:nativeCluster:1.0.0`
     to `urn:vcloud:type:cse:nativeCluster:2.0.0` entities.
   - Existing templates will no longer be recognized by CSE 3.1. 
   - It is strongly recommended to force recreate the templates from the new template cookbook. 
     CSE server needs at least one valid template in order to start.
   - Existing clusters must be upgraded to newer templates in order to enable operations like resize.
   - VCD's defined entity api can be used to initiate CRUD operations on the clusters.
    
Refer to [CSE 3.1 upgrade command](CSE_SERVER_MANAGEMENT.html#cse31-upgrade-cmd).

#### 2.2.3 Tenant onboarding
The provider needs to perform below operations to enable Kubernetes cluster
deployments in tenant organizations and tenant virtual data centers.
1. Grant rights to the tenant users. Refer to [CSE >= 3.0 RBAC](RBAC.html#DEF-RBAC)
for more details.
2. Enable the desired organization virtual datacenter(s) for either Native or
Tkg cluster or Ent-PKS deployments.
    * Tkg clusters → [Publish Kubernetes policy on VDC for Tkg Clusters](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-E9839D4E-3024-445E-9D08-372113CF6FE0.html)
    * Native clusters → [Enable VDC for Native clusters](TEMPLATE_MANAGEMENT.html#restrict_templates).
    * Ent-PKS clusters → [Enable VDC for Ent-PKS clusters](ENT_PKS.html#cse-commands)
3. [Publish Kubernetes Clusters UI Plugin](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html)
to the desired organizations.

### 2.3 Kubernetes Clusters UI Plugin
Kubernetes Clusters UI Plugin 3.0 is available out of the box with VCD 10.3. Provider can publish it to the desired tenants
to offer Kubernetes services. Refer to [publish Kubernetes Clusters UI Plugin](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html)
For VCD 10.2 that inter-operates with CSE 3.1, Provider must use the Kubernetes Clusters UI Plugin 2.0 that comes with VCD to offer Kubernetes Services.
For VCD < 10.2 versions that inter-operate with CSE 3.1, Kubernetes Clusters UI Plugin 1.0.3 must be installed separately by a Provider and published to the desired tenants.
Refer to [Register CSE UI Plugin 1.0.3](CSE_UI_PLUGIN.html) for more details.

<a name="tenant-workflows"></a>
## 3. Tenant workflows
Tenant users can manage the Kubernetes cluster deployments either through 
CSE CLI or Kubernetes Clusters UI Plugin

### 3.1 CLI for Container Extension
CSE 3.1 introduces below changes in CLI

1. Cluster upgrades (Native and vSphere with Tanzu) can now be performed using `vcd cse cluster apply <upgrade_cluster.yaml>`. 
   Refer to [cluster apply usage](CLUSTER_MANAGEMENT.html#cse30_cluster_apply) for more details.
2. Clusters can be shared to other users using new `vcd cse cluster share` command. 
   Refer to [cluster share usage](CLUSTER_MANAGEMENT.html#cse31_cluster_share)

### 3.2 Kubernetes Clusters UI Plugin

For VCD 10.3, you must use the [Kubernetes Clusters UI Plugin 3.0](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html
) that comes with VCD to manage the cluster deployments.
For VCD 10.2, you must use the [Kubernetes Clusters UI Plugin 2.0](https://docs.vmware.com/en/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-A1910FF9-B2CF-49DD-B031-D1245E8740AE.html
) that comes with VCD to manage the cluster deployments.

If you are working with VCD < 10.2, you must use the [Kubernetes Clusters UI
Plugin 1.0.3](CSE_UI_PLUGIN.html) to manage the cluster deployments.

<a name="faq"></a>
## 4. FAQ
Refer to [Troubleshooting](TROUBLESHOOTING.html) and [Known issues](KNOWN_ISSUES.html) pages.
