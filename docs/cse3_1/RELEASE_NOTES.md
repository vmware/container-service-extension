---
layout: default
title: Release Notes
---

# Release Notes

## CSE 3.1.1 Beta (3.1.1.0b1)
Release Date: 2021-09-13

**Supported (and tested) VCD versions**: 10.3.0 GA

Note: Future update/patch releases of these vCD versions will be supported by CSE but
they won't be tested individually. If a bug is found in their interoperability
with CSE, please file a github [issue](https://github.com/vmware/container-service-extension/issues),
the same will be fixed in a future CSE release.

| CSE Server | CSE CLI   | CSE UI | Cloud Director | NSX-V  | NSX-T with AVI             | Features offered              |
|------------|-----------|--------|----------------|--------|----------------------------|-------------------------------|
| 3.1.1.0b1  | 3.1.1.0b1 | 3.0.1* | 10.3           | 6.4.10 | NSX-T 3.1.1 and Avi 20.1.3 | Native, TKG-S and TKG         |
| NA         | 3.1.1.0b1 | 3.0.1* | 10.3           | NA     | NA                         | TKG-S cluster management only |

3.0.1* -> Please download Kubernetes Clusters UI Plugin from [here](www.vmware.com)  

**Installation of binaries**

```sh
pip install container-service-extension==3.1.1.0b1
```

Note: `pip install container-service-extension` installs previous official
version of CSE viz. 3.1.0. Specify the exact version mentioned above to install
CSE 3.1.1 beta.

**What's New**
* Support for importing standard TKG OVA and deploying Kubernetes clusters using them.
  * Supported TKG OVAs : TKG 1.4, 1.3.1 - Ubuntu 20.04 Kubernetes v1.20.5 vmware.2
* Kubernetes clusters based on TKG runtime with VCD CPI and VCD CSI
  * Learn more about [VCD CPI](https://github.com/vmware/cloud-provider-for-cloud-director/blob/0.1.0-beta/README.md)
  and [VCD CSI](https://github.com/vmware/cloud-director-named-disk-csi-driver/blob/0.1.0-beta/README.md)

**Notes to System Administrator**  
* CSE 3.1.1.0b1 is supposed to be a fresh install only release, and
won't support upgrades to CSE 3.1.1.
* Users deploying TKG clusters should have atleast the rights required to deploy
`exposed` native clusters and additionally the right `Full Control: CSE:NATIVECLUSTER`.
This right is crucial for VCD CPI to work properly.
* It is mandatory to deploy TKG clusters with `expose` field set to `True`. Read more
about `expose` functionality [here](CLUSTER_MANAGEMENT.html#expose_cluster).
Routablility of external network traffic to the cluster is crucial for VCD CPI to
work properly
* TKG clusters should be connected to a network that can access
the public end point of the VCD.

**Known issues**:  
Shrinking TKG clusters via `cse cluster apply` is not supported. If users
wish to shrink their TKG clusters, they need to use `kubectl` to do it.
  * On control plane node
    * `kubetcl cordon [node name]`
    * `kubectl drain [node name]`
    * `kubectl delete [node name]` (Optional, VCD CPI will update the state of the cluster once the actual worker VM is deleted)
  * On worker node
    * Once the commands on control plane node has succeddfully completed,
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

3.0*, 2.0* -> Kubernetes Clusters UI Plugins 3.0 and 2.0 ship with VCD 10.3 and VCD 10.2 respectively.

1. Refer to [What's new in CSE 3.1?](CSE31.html) for more details.
2. Newer versions of native kubernetes templates are available. Refer to
[Template Announcements](TEMPLATE_ANNOUNCEMENTS.html)

## CSE 3.1.0 Beta (3.1.0.0b1)
Release Date: 2021-04-14

Supported VCD versions: 10.3.0-Beta, 10.2.2, 10.1.3, 10.0.0.3

| CSE Server | CSE CLI | CSE UI  | Cloud Director       | Cloud Director NSX-T | Ent-PKS with NSX-T | Features offered                                                                                    |
|------------|---------|---------|----------------------|----------------------|--------------------|-----------------------------------------------------------------------------------------------------|
| 3.1.0      | 3.1.0   | 3.0.2** | 10.3.0-beta, 10.2.2  | 3.0.2, 3.1.2         | 1.7 with 2.5.1     | Native, Tkg, and Ent-PKS Cluster management; Defined entity representation for both native and tkg. |
| 3.1.0      | 3.1.0   | 1.0.3   | 10.1, 10.0           | NA                   | 1.7 with 2.5.1     | Native and Ent-PKS cluster management                                                               |
| NA         | 3.1.0   | 3.0.2** | 10.3.0-beta, 10.2.2  | NA                   | NA                 | Tkg cluster management only                                                                         |


**Installation of binaries**

```sh
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
