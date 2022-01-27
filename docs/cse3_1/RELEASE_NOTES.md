---
layout: default
title: Release Notes
---

# General Announcement
**Date : 2022-01-27**  
Container Service Extension 3.1.x reaches end of support on July 15, 2023.  
Tanzu Kubernetes Grid Integrated Edition (TKG-I) is no longer supported.

**Date : 2021-12-15**  
CSE is not impacted by the Apache Log4j open source component vulnerability.

# Release Notes

## CSE 3.1.2 GA (3.1.2)
Release Date : 2022-01-27

**Supported (and tested) VCD versions**: 10.3.2 GA, 10.3.1 GA, 10.2.2 GA, 10.1.3 GA

Note: Future update/patch releases of these VCD versions will be supported by CSE but
they won't be tested individually. If a bug is found in their interoperability
with CSE, please file a github [issue](https://github.com/vmware/container-service-extension/issues),
the same will be fixed in a future CSEs release.

* Check out [what's new](CSE31.html) in this release.
* Compatility matrix for CSE 3.1.2 can be found [here](CSE31.html#cse31-compatibility-matrix).

**Notes to System Administrator**:
* Please take note of the supported upgrade paths for CSE 3.1.2 [here](CSE31.html#brown_field_upgrades).

## CSE 3.1.1 GA (3.1.1)
Release Date : 2021-10-14

**Supported (and tested) VCD versions**: 10.3.1 GA, 10.2.2 GA, 10.1.3 GA

Note: Future update/patch releases of these VCD versions will be supported by CSE but
they won't be tested individually. If a bug is found in their interoperability
with CSE, please file a github [issue](https://github.com/vmware/container-service-extension/issues),
the same will be fixed in a future CSE release.

* Check out [what's new](CSE31.html) in this release.
* Compatility matrix for CSE 3.1.1 can be found [here](CSE31.html#cse31-compatibility-matrix).

**Notes to System Administrator**:
* Please take note of the supported upgrade paths for CSE 3.1.1 [here](CSE31.html#brown_field_upgrades).
* Upgrading CSE from beta builds of CSE 3.1.1 to CSE 3.1.1 GA is not recommended nor supported.

## CSE 3.1.1 Beta 2 (3.1.1.0b2)
Release Date: 2021-09-21

**Supported (and tested) VCD versions**: 10.3.0 GA

Note: Future update/patch releases of these VCD versions will be supported by CSE but
they won't be tested individually. If a bug is found in their interoperability
with CSE, please file a github [issue](https://github.com/vmware/container-service-extension/issues),
the same will be fixed in a future CSE release.

| CSE Server | CSE CLI   | CSE UI | Cloud Director | NSX-T with Avi             | Features offered |
|------------|-----------|--------|----------------|----------------------------|------------------|
| 3.1.1.0b2  | 3.1.1.0b2 | 3.0.4* | 10.3           | NSX-T 3.1.1 and Avi 20.1.3 | TKG              |

3.0.4* -> Please download Kubernetes Container Clusters UI Plugin from [here](https://github.com/vmware/container-service-extension/raw/master/cse_ui/3.0.4/container-ui-plugin.zip)

**Installation of binaries**
```
pip install container-service-extension==3.1.1.0b2
```
Note: `pip install container-service-extension` installs previous official
version of CSE viz. 3.1.0. Specify the exact version mentioned above to install
CSE 3.1.1 beta.

**What's New**
* Support for importing VMware Tanzu Kubernetes Grid OVA and deploying Kubernetes clusters using them.
  * Learn more about using [VMware Tanzu Kubernetes Grid OVA with CSE](TEMPLATE_MANAGEMENT.html#tkgm_templates)
  * Learn more about deploying a Kubernetes cluster based on VMware Tanzu Kubernetes Grid [here](CLUSTER_MANAGEMENT.html#tkgm_clusters)
* VCD CPI and VCD CSI for Kubernetes clusters based on VMware Tanzu Kubernetes Grid
  * Learn more about [VCD CPI](https://github.com/vmware/cloud-provider-for-cloud-director/blob/0.1.0-beta/README.md)
  and [VCD CSI](https://github.com/vmware/cloud-director-named-disk-csi-driver/blob/0.1.0-beta/README.md)
* Provision to deploy `Exposed` clusters from Kubernetes Container Clusters UI
* CSE now pulls Antrea from Harbor repository instead of DockerHub

**Supported VMware Tanzu Kubernetes Grid OVAs**
* VMware Tanzu Kubernetes Grid 1.3.0 : Ubuntu 20.04, Kubernetes v1.20.4 vmware.1 (ubuntu-2004-kube-v1.20.4-vmware.1-tkg.0-16153464878630780629.ova)
* VMware Tanzu Kubernetes Grid 1.3.1 : Ubuntu 20.04, Kubernetes v1.20.5 vmware.2 (ubuntu-2004-kube-v1.20.5-vmware.2-tkg.1-6700972457122900687.ova)
* VMware Tanzu Kubernetes Grid 1.4.0 : Ubuntu 20.04, Kubernetes v1.21.2 vmware.1 (ubuntu-2004-kube-v1.21.2+vmware.1-tkg.1-7832907791984498322.ova)

**Notes to System Administrator**
* CSE 3.1.1.0b2 is supposed to be a fresh install only release, and
won't support upgrades to CSE 3.1.1.
* It is mandatory to deploy VMware Tanzu Kubernetes Grid clusters with `expose` field set to `True`.
Read more about `expose` functionality [here](CLUSTER_MANAGEMENT.html#expose_cluster).
Routability of external network traffic to the cluster is crucial for VCD CPI to
work properly.
* Users deploying VMware Tanzu Kubernetes Grid clusters should have the rights required
to deploy `exposed` native clusters and additionally the right `Full Control: CSE:NATIVECLUSTER`.
This right is crucial for VCD CPI to work properly. [VCD CPI](https://github.com/vmware/cloud-provider-for-cloud-director/blob/0.1.0-beta/README.md)
and [VCD CSI](https://github.com/vmware/cloud-director-named-disk-csi-driver/blob/0.1.0-beta/README.md)
docs list down all rights required for their proper functioning.
* VMware Tanzu Kubernetes Grid clusters should be connected to a network that can access
the public end point of the VCD. This network **should** have DNS setup, the same DNS server
would be used by all cluster vms for name resolution while reaching out to internet to
download Antrea, VCD CPI and VCD CSI.


**Known issues**:
Scaling down Kubernetes clusters  via `cse cluster apply` does not drain the worker nodes
properly and can lead to loss in application data. If users wish to shrink their TKG clusters,
they need to use `kubectl` to do it.
  * On control plane node
    * `kubetcl cordon [node name]`
    * `kubectl drain [node name]`
    * `kubectl delete [node name]` (Optional, VCD CPI will update the state of the cluster once the actual worker VM is deleted)
  * On worker node
    * Once the commands on control plane node have successfully completed,
      power off the vm and delete it from VCD UI


## CSE 3.1.1 Beta 1 (3.1.1.0b1)
Release Date: 2021-09-13

**Supported (and tested) VCD versions**: 10.3.0 GA

Note: Future update/patch releases of these VCD versions will be supported by CSE but
they won't be tested individually. If a bug is found in their interoperability
with CSE, please file a github [issue](https://github.com/vmware/container-service-extension/issues),
the same will be fixed in a future CSE release.

| CSE Server | CSE CLI   | CSE UI | Cloud Director | NSX-T with Avi             | Features offered |
|------------|-----------|--------|----------------|----------------------------|------------------|
| 3.1.1.0b1  | 3.1.1.0b1 | 3.0.1* | 10.3           | NSX-T 3.1.1 and Avi 20.1.3 | TKG              |

3.0.1* -> Please download Kubernetes Container Clusters UI plugin from [here](https://github.com/vmware/container-service-extension/raw/master/cse_ui/3.0.1/container-ui-plugin.zip)

**Installation of binaries**
```
pip install container-service-extension==3.1.1.0b1
```
Note: `pip install container-service-extension` installs previous official
version of CSE viz. 3.1.0. Specify the exact version mentioned above to install
CSE 3.1.1 beta.

**What's New**
* Support for importing VMware Tanzu Kubernetes Grid OVA and deploying Kubernetes clusters using them.
  * Learn more about using [VMware Tanzu Kubernetes Grid OVA with CSE](TEMPLATE_MANAGEMENT.html#tkgm_templates)
  * Learn more about deploying a Kubernetes cluster based on VMware Tanzu Kubernetes Grid [here](CLUSTER_MANAGEMENT.html#tkgm_clusters)
* VCD CPI and VCD CSI for Kubernetes clusters based on VMware Tanzu Kubernetes Grid
  * Learn more about [VCD CPI](https://github.com/vmware/cloud-provider-for-cloud-director/blob/0.1.0-beta/README.md)
  and [VCD CSI](https://github.com/vmware/cloud-director-named-disk-csi-driver/blob/0.1.0-beta/README.md)

**Supported VMware Tanzu Kubernetes Grid OVAs**
* VMware Tanzu Kubernetes Grid 1.3.0 : Ubuntu 20.04, Kubernetes v1.20.4 vmware.1 (ubuntu-2004-kube-v1.20.4-vmware.1-tkg.0-16153464878630780629.ova)
* VMware Tanzu Kubernetes Grid 1.3.1 : Ubuntu 20.04, Kubernetes v1.20.5 vmware.2 (ubuntu-2004-kube-v1.20.5-vmware.2-tkg.1-6700972457122900687.ova)
* VMware Tanzu Kubernetes Grid 1.4.0 : Ubuntu 20.04, Kubernetes v1.21.2 vmware.1 (ubuntu-2004-kube-v1.21.2+vmware.1-tkg.1-7832907791984498322.ova)

**Notes to System Administrator**
* CSE 3.1.1.0b1 is supposed to be a fresh install only release, and
won't support upgrades to CSE 3.1.1.
* It is mandatory to deploy VMware Tanzu Kubernetes Grid clusters with `expose` field set to `True`.
Read more about `expose` functionality [here](CLUSTER_MANAGEMENT.html#expose_cluster).
Routability of external network traffic to the cluster is crucial for VCD CPI to
work properly.
* Users deploying VMware Tanzu Kubernetes Grid clusters should have the rights required
to deploy `exposed` native clusters and additionally the right `Full Control: CSE:NATIVECLUSTER`.
This right is crucial for VCD CPI to work properly. [VCD CPI](https://github.com/vmware/cloud-provider-for-cloud-director/blob/0.1.0-beta/README.md)
and [VCD CSI](https://github.com/vmware/cloud-director-named-disk-csi-driver/blob/0.1.0-beta/README.md)
docs list down all rights required for their proper functioning.
* VMware Tanzu Kubernetes Grid clusters should be connected to a network that can access
the public end point of the VCD.

**Known issues**:
Scaling down Kubernetes clusters  via `cse cluster apply` does not drain the worker nodes
properly and can lead to loss in application data. If users wish to shrink their TKG clusters,
they need to use `kubectl` to do it.
  * On control plane node
    * `kubetcl cordon [node name]`
    * `kubectl drain [node name]`
    * `kubectl delete [node name]` (Optional, VCD CPI will update the state of the cluster once the actual worker VM is deleted)
  * On worker node
    * Once the commands on control plane node have successfully completed,
      power off the vm and delete it from VCD UI


## CSE 3.1.0
Release Date: 2021-07-15

**Supported (and tested) VCD versions**: 10.3, 10.2, 10.1

Note: Future update/patch releases of these vCD versions will be supported by CSE but
they won't be tested individually. If a bug is found in their interoperability
with CSE, please file a github [issue](https://github.com/vmware/container-service-extension/issues),
the same will be fixed in a future CSE release.

| CSE Server | CSE CLI | CSE UI | Cloud Director | Ent-PKS with NSX-T | NSX-V  | Features offered                                                                                    |
|------------|---------|--------|----------------|--------------------|--------|-----------------------------------------------------------------------------------------------------|
| 3.1        | 3.1     | 3.0*   | 10.3           | 1.7 with 2.5.1     | 6.4.10 | Native, TKG-S, and Ent-PKS Cluster management;                                                      |
| 3.1        | 3.1     | 2.0*   | 10.2           | 1.7 with 2.5.1     | 6.4.10 | Native, TKG-S, and Ent-PKS Cluster management; Defined entity representation for both native and tkg. |
| 3.1        | 3.1     | 1.0.3  | 10.1           | 1.7 with 2.5.1     | 6.4.8  | Native and Ent-PKS cluster management                                                               |
| NA         | 3.1     | 3.0*   | 10.3           | NA                 | NA     | TKG-S cluster management only                                                                         |
| NA         | 3.1     | 2.0*   | 10.2           | NA                 | NA     | TKG-S cluster management only                                                                         |

3.0*, 2.0* -> Kubernetes Container Clusters UI plugin 3.0 and 2.0 ship with VCD 10.3 and VCD 10.2 respectively.

1. Refer to [What's new in CSE 3.1?](CSE31.html) for more details.
2. Newer versions of native kubernetes templates are available. Refer to
[Template Announcements](TEMPLATE_ANNOUNCEMENTS.html)
1. Deprecation of TKG-I (Enterprise PKS) - CSE Server and Kubernetes Container Clusters UI plugin
will soon drop support for TKG-I (previously known as Enterprise PKS). Consider using
VMware Tanzu Kubernetes Grid (TKG) or VMware Tanzu Kubernetes Grid Service (TKG-S) for
management of Kubernetes clusters with VCD.

## CSE 3.1.0 Beta (3.1.0.0b1)
Release Date: 2021-04-14

Supported VCD versions: 10.3.0-Beta, 10.2.2, 10.1.3, 10.0.0.3

| CSE Server | CSE CLI | CSE UI  | Cloud Director       | Cloud Director NSX-T | Ent-PKS with NSX-T | Features offered                                                                                    |
|------------|---------|---------|----------------------|----------------------|--------------------|-----------------------------------------------------------------------------------------------------|
| 3.1.0      | 3.1.0   | 3.0.2** | 10.3.0-beta, 10.2.2  | 3.0.2, 3.1.2         | 1.7 with 2.5.1     | Native, Tkg, and Ent-PKS Cluster management; Defined entity representation for both native and tkg. |
| 3.1.0      | 3.1.0   | 1.0.3   | 10.1, 10.0           | NA                   | 1.7 with 2.5.1     | Native and Ent-PKS cluster management                                                               |
| NA         | 3.1.0   | 3.0.2** | 10.3.0-beta, 10.2.2  | NA                   | NA                 | Tkg cluster management only                                                                         |


**Installation of binaries**

```
pip install container-service-extension==3.1.0.0b1
```

Note: `pip install container-service-extension` installs previous official
version of CSE viz. 3.0.2. Specify the above mentioned exact version to install
CSE 3.1.0 beta.

**What's New**
* Tenant UI plugin supports cluster upgrades for both Native and Tanzu clusters
* PUT on `/api/cse/3.0/cluster/<id>` endpoint now supports cluster upgrades in addition to the resize operation.
    * `/api/cse/3.0/cluster/<id>/action/upgrade` is not supported at api_version = 36.0
* Cluster YAML specification changes
    * Keys of all the properties are expected to be in CamelCase.
    * New required field `apiVersion` in the cluster YAML specification. The
      value for it must be `cse.vmware.com/v2.0`, which indicates the RDE version
      of the native clusters, that CSE server uses.
    * Sample input YAML
        * ```
          apiVersion: cse.vmware.com/v2.0
          kind: native
          metadata:
            name: mycluster
            orgName: myorg
            ovdcName: myorgvdc
            site: vcd.eng.vmware.com
          spec:
            controlPlane:
              count: 1
              sizingClass: null
              storageProfile: null
            k8Distribution:
              templateName: ubuntu-16.04_k8-1.18_weave-2.6.5
              templateRevision: 2
            nfs:
              count: 0
              sizingClass: null
              storageProfile: null
            settings:
              network: mynet
              rollbackOnFailure: true
              sshKey: ''
            workers:
              count: 0
              sizingClass: null
              storageProfile: null
          ```
* Improved performance for ovdc and cluster listing commands

**Notes to System Administrator**
If you are upgrading from an existing CSE 3.0.x installation please be aware of
the issue related to runtime defined entities listed in [Known Issues](KNOWN_ISSUES.html).

**Known issues specific to 3.1.0-beta**:
Resizing an empty cluster will fail for non-null values of sizingClass and storageProfile in the input yaml spec.
Workaround: specify `storageProfile: null` and `sizingClass: null` in
the `vcd cse cluster apply` specification for worker/nfs nodes.
