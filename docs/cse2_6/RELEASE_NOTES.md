---
layout: default
title: Release Notes
---

# General Announcement
**Date : 2022-01-27**  
Container Service Extension 2.6.x reaches end of support on April 9, 2022.  
Container Service Extension 2.5.x has reached end of support on October 3, 2021.  
Container Service Extension 2.0.x has reached end of support on May 24, 2021.
Tanzu Kubernetes Grid Integrated Edition (TKG-I) is no longer supported.


# Release Notes

## CSE 2.6.1 GA(2.6.1)
Release Date: 2020-04-30

**Supported (and Tested) VCD versions** : 9.5.0.4, 9.7.0.4, 10.0.0.1, 10.1.0

Note : Future update/patch releases of these vCD versions will be supported by CSE but
they won't be tested individually. If a bug is found in their interoperability
with CSE, please file a github [issue](https://github.com/vmware/container-service-extension/issues),
the same will be fixed in a future CSE release.

Enterprise PKS compatibility matrix

|CSE   | VCD                                      | Enterprise PKS | NSX-T | Support status           |
|------|------------------------------------------|----------------|-------|--------------------------|
|2.6.1 | 9.5.0.4, 9.7.0.4, 10.0.0.1, 10.1.0.0     | 1.7            | 2.5.1 | Supported and Tested     |
|2.6.1 | 9.5.0.5+, 9.7.0.5+, 10.0.0.2+, 10.1.0.1+ | 1.7            | 2.5.1 | Supported but not Tested |

CSE UI plugin compatibility matrix

|CSE   | VCD       | CSE UI plugin | Support status           |
|------|-----------|---------------|--------------------------|
|2.6.1 | 10.1.0.0  | 1.0.1         | Supported and Tested     |
|2.6.1 | 10.1.0.1+ | 1.0.1         | Supported but not Tested |

**What's New**
* Support for Enterprise PKS 1.7 (and NSX-T 2.5.1).
  * Enterprise PKS 1.4 and NSX-T 2.3/2.4 are no longer supported.
* New patch version of CSE UI Plugin (v1.0.1) is now available
  * Fixed bug where network gateway CIDR shows netmask instead of gateway IP
  * Fixed bug where cluster/node creation wizard does not show shared ovdc networks
  * PKS clusters now display Kubernetes version
  * Read more about it [here](/container-service-extension/CSE_UI_PLUGIN.html)

**Notes to System Administrator**

If you are upgrading to CSE 2.6.1 from an older version of CSE, and you have
* Kubernetes 1.15, 1.16 or 1.17 based template created by CSE 2.5.x:
  * You must recreate/replace those templates with their latest version available.
* Pre-existing deployed native K8s clusters, you must run the following command:
  ```sh
  cse convert-cluster [cluster name]
  ```
  * From CSE 2.5.x - To be able to upgrade the clusters.
  * From CSE older than 2.5.0 - To preserve manageability of the clusters.

This command adds new metadata to the clusters. If the clusters were deployed
by CSE version below 2.5.0, the command will also reset the admin password of
all nodes in the clusters. If nodes in the clusters were setup with ssh keys
for root login, those key pairings will be preserved. The command will force a
reboot of the clusters, if admin password is reset.

**Enterprise PKS**

Existing Enterprise PKS clusters deployed via CSE will continue to function
when PKS is upgraded to version 1.7. The cluster network isolation will also
remain intact when NSX-T is upgraded to version 2.5.1. Please follow PKS and
NSX-T manual(s) to perform the respective upgrades.

---

## CSE 2.6.0 GA(2.6.0)
Release Date: 2020-04-09

Supported VCD versions: 9.5.0.4, 9.7.0.4, 10.0.0.1, 10.1.0

Enterprise PKS compatibility matrix

|CSE   | VCD                                | Enterprise PKS | NSX-T    |
|------|------------------------------------|----------------|----------|
|2.6.0 | 9.5.0.4, 9.7.0.4, 10.0.0.1, 10.1.0 | 1.4            | 2.3, 2.4 |

CSE UI plugin compatibility matrix

|CSE   | VCD    | CSE UI plugin |
|------|--------|---------------|
|2.6.0 | 10.1.0 | 1.0.0         |


**New Features**
* New Templates with updated Kubernetes and Weave
  * [Template Announcements](TEMPLATE_ANNOUNCEMENTS.html)
* In place Kubernetes upgrade for clusters
  * CSE offers the new capability to do in place upgrade of Kubernetes
    related software in Native clusters. More details
    [here](CLUSTER_MANAGEMENT.html#k8s_upgrade).
* Secure Configuration files
  * CSE now supports encrypted configuration files. More details
  [here](CSE_CONFIG.html#encrypt_decrypt).
* CSE UI Plugin for VCD
  * Read more about it [here](CSE_UI_PLUGIN.html)
* Interoperability with VCD 10.1.0

**Notes to System Administrator**

Upgrade from CSE 2.6.0.0b1 is not supported.

If you are upgrading to CSE 2.6.0 from an older version of CSE, and you have
pre-existing deployed K8s clusters, you must run the following command:
```sh
cse convert-cluster
```
* From CSE 2.5.0 or above - To be able to upgrade the cluster.
* From CSE older than 2.5.0 - To preserve managablilty of the clusters.

This command adds new metadata to the cluster. If the cluster was deployed by 
CSE version below 2.5.0, the command will also reset the admin password of all
nodes in the cluster. If nodes in the cluster are setup with ssh keys for root
login, those key pairings will be preserved. The command will force a
reboot of the cluster, if admin password is reset.

---

## CSE 2.6.0 Beta (2.6.0.0b1)
Release Date: 2020-02-05

Supported VCD versions: 9.5.0.4, 9.7.0.4, 10.0.0.1, 10.1.0

Enterprise PKS compatibility matrix

|CSE       | VCD                                     | Enterprise PKS | NSX-T    |
|----------|-----------------------------------------|----------------|----------|
|2.6.0.0b1 | 9.5.0.4, 9.7.0.4, 10.0.0.1, 10.1.0-Beta | 1.4            | 2.3, 2.4 |

**Installation of binaries**

```sh
pip install container-service-extension==2.6.0.0b1
# or
pip install container-service-extension --pre
```

Note: `pip install container-service-extension` installs previous official
version of CSE viz. 2.5.1. Specify the above mentioned exact version to install
CSE 2.6.0 beta.

**New Features**

* New Templates with updated Kubernetes and Weave
  * [Template Announcements](TEMPLATE_ANNOUNCEMENTS.html)
* In place Kubernetes upgrade for clusters
  * CSE offers the new capability to do in place upgrade of Kubernetes
    related software in Native clusters. More details
    [here](CLUSTER_MANAGEMENT.html#k8s_upgrade).
* Secure Configuration files
  * CSE now supports encrypted configuration files. More details
  [here](CSE_CONFIG.html#encrypt_decrypt).
* CSE UI Plugin for VCD
  * Read more about it [here](CSE_UI_PLUGIN.html)
* Interoperability with VCD 10.1.0 Beta

**Notes to System Administrator**

If you are upgrading to CSE 2.6.0.0b1 and you have pre-existing K8s clusters
deployed from CSE 2.5.1 or below, you must run the following command to
preserve manageability of those clusters in CSE 2.6.0.0b1.
```sh
cse convert-cluster
```
This command resets the admin password of all nodes in the clusters deployed by
CSE 2.0.0 and below. The command also formats the metadata on the cluster to
match CSE 2.6.0.0b1's cluster metadata format. If nodes in the cluster are setup
with ssh keys for root login, those key pairings will be preserved. The command
does a force reboot of the cluster deployed by CSE 2.0.0 and below.

---

## CSE 2.5.1

Release Date: 2019-10-23

Supported VCD versions: 9.1, 9.5, 9.7, 10.0

Enterprise PKS compatibility matrix

|CSE | VCD |Enterprise PKS| NSX-T |
|-|-|-|-|
|2.5.0 | 9.1, 9.5, 9.7, 10.0  | 1.4 | 2.3, 2.4 |

**New Features**
* New Template revisions with updated Kubernetes
  * [Template Announcements](TEMPLATE_ANNOUNCEMENTS.html)

**Bug Fixes**
* Fixed known issue where users are unable to start CSE 2.5 server if a new compute policy is defined in the template_rules section of the CSE server config file
* Fixed known issue where 'cluster create' command fails if the '--nodes/-N' option is missing.

---

## CSE 2.5.0

Release Date: 2019-10-03

Supported VCD versions: 9.1, 9.5, 9.7, 10.0

Enterprise PKS compatibility matrix

|CSE | VCD |Enterprise PKS| NSX-T |
|-|-|-|-|
|2.5.0 | 9.1, 9.5, 9.7, 10.0  | 1.4 | 2.3, 2.4 |

**New Features**
* New Templates with updated Kubernetes and Weave
  * [Template Announcements](TEMPLATE_ANNOUNCEMENTS.html)
* Multiple Kubernetes Templates
  * CSE now offers the new capability to use variety of
    Kubernetes templates in real time for Kubernetes cluster deployments. With
    that also comes the complete offering of Kubernetes templates life-cycle
    management for Service Providers. More details
    [here](TEMPLATE_MANAGEMENT.html#kubernetes_templates).
* Remote Repository for Kubernetes Templates
  * Service Providers can fetch  new and/or revised Kubernetes templates from
  remote repository without updating CSE (Exception - bug fixes and new
  features will require newer CSE versions). More details
  [here](TEMPLATE_MANAGEMENT.html#creating_kubernetes_templates).

**Notes to System Administrator**

Upgrade from CSE 2.5.0.0b1 is not supported.


If you are upgrading to CSE 2.5.0 from any other version of CSE, and you have
preexisting deployed K8s clusters, you must run the following command to
preserve manageability of those clusters in CSE 2.5.0.
```sh
cse convert-cluster
```
This command resets the admin password of all nodes in the cluster, as well as,
adds new metadata to the cluster. If nodes in the cluster are setup with
ssh keys for root login, those key pairings will be preserved. The command does
a force reboot of the cluster.

---

## CSE 2.5.0 Beta (2.5.0.0b1)

Release Date: 2019-09-06

Supported VCD versions: 9.1, 9.5, 9.7

| Template OS | Docker | Kubernetes | Pod Network |
|-|-|-|-|
| Photon OS 2.0 GA | 18.06.2 | 1.12.7 | Weave 2.3.0 |
| Ubuntu 16.04 LTS | 18.09.7 | 1.13.5 | Weave 2.3.0 |
| Ubuntu 16.04 LTS | 18.09.7 | 1.15.3 | Weave 2.5.2 |

**Installation of binaries**

```sh
pip install container-service-extension==2.5.0.0b1
```

or

```sh
pip install container-service-extension --pre
```

Note: `pip install container-service-extension` installs previous official
version of CSE - 2.0.0. Specify the above mentioned exact version to install
CSE 2.5.0 beta.

**New Features**

- Support for multiple K8s templates

**Compatibility matrix**

|CSE | VCD |Enterprise PKS| NSX-T |
|-|-|-|-|
|2.5.0 Beta | 9.1, 9.5, 9.7  | 1.4 | 2.3, 2.4 |

**Notes to System Administrator**

If you are upgrading to CSE 2.5.0.0b1 and you have pre-existing K8s clusters
deployed from CSE 2.0.0 or below, you must run the following command to
preserve manageability of those clusters in CSE 2.5.0.0b1.
```sh
cse convert-cluster
```
This command resets the admin password of all nodes in the cluster, as well as,
adds new metadata to the cluster. If nodes in the cluster are setup with
ssh keys for root login, those key pairings will be preserved. The command does
a force reboot of the cluster.

---

## CSE 2.0.0

Release Date: 2019-05-24

Supported VCD versions: 9.1, 9.5, 9.7.

**Native VCD Templates**

Native VCD templates need to be updated to avail below versions of K8 distributions.

| Template OS        | Docker                 | Kubernetes | Pod Network |
|--------------------|------------------------|------------|-------------|
| Photon OS 2.0 GA   | 17.06.0-9 (17.06.0-ce) | 1.12.7     | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.06.3-ce             | 1.13.5     | Weave 2.3.0 |

**New Updates**

- [Enterprise PKS enablement](ENT_PKS.html) - CSE
now supports new K8 provider Enterprise PKS in addition to Native VCD as K8 provider.
- [Role based access control](RBAC.html) - Enabling
 this feature allows users granted with specific K8 rights only to deploy K8 clusters.
- Python version has to be >= 3.7.3. This change has been made in order to address
[CVE-2019-9636](https://nvd.nist.gov/vuln/detail/CVE-2019-9636)

**Enterprise PKS Compatibility matrix**

|CSE      | Supported VCD Versions |Enterprise PKS| NSX-T |
|---------|------------------------|--------------|-------|
|2.0.0    | 9.5, 9.7               | 1.4          | 2.3   |
|2.0.0    | 9.5, 9.7               | 1.4          | 2.4   |

**Notes to System Administrator**

When more than one K8 provider exists in the system, system administrator is required to
perform an extra step of enabling organization vdc(s) with a desired K8 provider
(Native/Enterprise PKS).

To be specific,
- If Enterprise PKS is not in the set up, users are allowed to deploy K8 clusters in any organization vdc.
- If Enterprise PKS is present in the CSE set up, users are allowed to deploy K8 clusters only in those
organization vdc(s) enabled either for Native (or) Enterprise PKS.

Click [here](CSE_CONFIG.html#pksconfig) for more details.

**VCD Native templates patching**

Action required (by Admins and Users)

* Cloud Admin:
    * Update CSE to 2.0.0
    * Update the templates
    * Command for updating template -> cse install -c config.yaml --template template-name --update --ext skip

* Tenant Users:
    * Delete clusters that were created with older templates. Recreate clusters with new templates
    * Alternatively, tenant-users can update docker version manually on existing clusters

---

## CSE 2.0 Beta (2.0.0.0b1)

**This version is meant to be used for fresh installations of CSE only**

Release Date: 2019-04-26

Supported VCD versions: 9.5, 9.7

| Template OS        | Docker                 | Kubernetes | Pod Network |
|--------------------|------------------------|------------|-------------|
| Photon OS 2.0 GA   | 17.06.0-9 (17.06.0-ce) | 1.10.11    | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.06.3-ce             | 1.13.5     | Weave 2.3.0 |

**Installation of binaries**
- `pip install container-service-extension==2.0.0.0b1` (or)
- `pip install container-service-extension --pre`

Note: `pip install container-service-extension` installs previous official
 version of CSE - 1.2.7. Specify the above mentioned exact version to install
 CSE 2.0 beta.

**New Features**

- [Enterprise PKS enablement](ENT_PKS.html)
- [Role based access control](RBAC.html)

**Compatibility matrix**

|CSE      | VCD       |Enterprise PKS| NSX-T |
|---------|-----------|--------------|-------|
|2.0 Beta | 9.5, 9.7  | 1.4          | 2.3   |

---

## CSE 1.2.7

Release Date: 2019-02-15

Supported VCD versions: 9.1, 9.5

| Template OS        | Docker                 | Kubernetes | Pod Network |
|--------------------|------------------------|------------|-------------|
| Photon OS 2.0 GA   | 17.06.0-9 (17.06.0-ce) | 1.10.11    | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.06.2-ce             | 1.10.11    | Weave 2.3.0 |

**Bug Fixes**

- Updated Docker package to address CVE-2019-5736 for both Ubuntu and Photon OS templates.
- `cluster config` command has been fixed (issue #225)

**Systems Patching**

Action required (by Admins and Users)

* Cloud Admin:
    * Update CSE to 1.2.7
    * Update the templates
    * Command for updating template -> cse install -c config.yaml --template template-name --update --ext skip

* Tenant Users:
    * Delete clusters that were created with older templates. Recreate clusters with new templates
    * Alternatively, tenant-users can update docker version manually on existing clusters

**Known Issues:**

* CSE installation fails on VCD 9.0 with MissingLinkException. No known fix yet.

---

## CSE 1.2.6

Release Date : 2019-02-04

Supported VCD versions: 9.1, 9.5

| Template OS        | Docker     | Kubernetes | Pod Network |
|:-------------------|:-----------|:-----------|:------------|
| Photon OS 2.0 GA   | 17.06.4-ce | 1.10.11    | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.11    | Weave 2.3.0 |

**New Feature:**

* Role based access control for deployment of kubernetes cluster
  * New config file key `enforce_authorization` under `service` section. Please refer to [config file documentation](CSE_CONFIG.html#service_section)
* Improved logging and error messages.

**Bug Fixes:**

* Changed default AMQP exchange to cse-ext. CSE will no longer use or update VCD's global exchange settings.
* A user can delete a partially deployed cluster which resulted from a failed cluster deployment operation.

**Known Issues:**

* CSE installation fails on VCD 9.0 with MissingLinkException.
* No known fix yet.

---

## CSE 1.2.5

Release date: 2018-12-03

This is a security release to address Kubernetes CVE-2018-1002105

Supported VCD versions: 9.0, 9.1, 9.5

| Template OS        | Docker     | Kubernetes | Pod Network |
|:-------------------|:-----------|:-----------|:------------|
| Photon OS 2.0 GA   | 17.06.4-ce | 1.10.11    | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.11    | Weave 2.3.0 |

**Bug Fixes:**

- Updated Kubernetes packages and docker images to address CVE-2018-1002105 for both Ubuntu and Photon OS templates.

**Systems patching:**

* Action required (by Admins and Users)

* Cloud Admin:
    * Update CSE to 1.2.5
    * Update the templates
    * Command for updating template -> cse install -c config.yaml --template template-name --update --amqp skip --ext skip

* Tenant Users:
    * Delete clusters that were created with older templates (with older K8 versions of 1.9.1 and 1.10.1). Recreate clusters with new templates (with latest K8 version of 1.10.11).
    * Alternatively, tenant-users can update kubernetes packages and docker images manually on existing clusters

---

## CSE 1.2.4

Release date: 2018-11-26

Supported VCD versions: 9.0, 9.1, 9.5

| Template OS        | Docker     | Kubernetes | Pod Network |
|:-------------------|:-----------|:-----------|:------------|
| Photon OS 2.0 GA   | 17.06.4-ce | 1.9.1      | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.1     | Weave 2.3.0 |

**New Feature:**

* Enabled NFS support for Photon OS

**Usability Improvements and Bug Fixes:**

* Revamped CSE Installation
    * `--update` option now removes CSE entities (vapps, ova files) before creating new templates.
    * Improved console output and error messages to be more clearly represent what actions are taking place during installation.
    * Added config file validation using `cse check`
    * Updated CSE installation validation to use `cse check -i`
* Fixed bug where control plane node creation fails during cluster create command.

**Documentation:**

* Added list of minimum required user rights for a CSE Service account (#152)

---

## CSE 1.2.3

Replaced with 1.2.4 due to bug where control plane node creation fails during cluster create command.

---

## CSE 1.2.2

Release date: 2018-10-29

Supported VCD versions: 9.0, 9.1, 9.5

| Template OS        | Docker     | Kubernetes | Pod Network |
|:-------------------|:-----------|:-----------|:------------|
| Photon OS 2.0 GA   | 17.06.4-ce | 1.9.1      | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.1     | Weave 2.3.0 |

**Bug Fixes:**

* Help option for commands (`vcd cse --help`) no longer requires login (#137)
* Fixed SSL support for vCenter 6.7 (#135)

---

## CSE 1.2.1

Release date: 2018-10-23

Supported VCD versions: 9.0, 9.1, 9.5

| Template OS        | Docker     | Kubernetes | Pod Network |
|:-------------------|:-----------|:-----------|:------------|
| Photon OS 2.0 GA   | 17.06.4-ce | 1.9.1      | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.1     | Weave 2.3.0 |

**Usability Improvements and Bug Fixes:**

* Add `status` display for `vcd cse cluster list`
* Updated pyvcloud requirement to >= 20.0.1 (#138)
* Fixed bug in setup files where CSE script files would not be downloaded properly to Windows systems from PyPI.
* Fixed bug where AMQP exchange would not be created if VCD and config file settings were the same.

**Documentation:**

* Updated CSE main documentation (#132)
* Updated docstrings (in code) for commands (#133)
* Updated help text during cluster creation

---

## CSE 1.2.0

Release date: 2018-10-02

Supported VCD versions: 9.0, 9.1, 9.5

| Template OS        | Docker     | Kubernetes | Pod Network |
|:-------------------|:-----------|:-----------|:------------|
| Photon OS 2.0 GA   | 17.06.4-ce | 1.9.1      | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.1     | Weave 2.3.0 |

**Security Improvements:**

* Updated ova file hashing to use SHA256 instead of SHA1 (#105)
* Added safeguards to file reading (#102)
* Users now are required to provide vCenter service account (#91)
* Added `--ssh-key` option for cse install (#114)
* Restricted permissions when setting up iptables-ports service (#103)

**Usability Improvements and Bug Fixes:**

* Fixed AMQP settings display bug, where settings that were different between VCD and config file were displayed out of order.
* If current vcd settings are same as config file, AMQP configuration is skipped.
* Fixed grub issue in ubuntu customization script, where user would be prompted with a selection menu, causing installation to hang.
* CSE installation now always shares templates.
* pyvcloud, vcd-cli version requirement update

**Documentation:**

* CSE License files uploaded
* Updated known issues section
* Listed required privileges for VCD service account
* Updated CSE-VCD compatibility matrix (#109)

---

## CSE 1.1.0

Release date: 2018-06-15

| VCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.4-ce | 1.9.1      | Weave 2.3.0 |
| 8.10 and up | Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.1     | Weave 2.3.0 |

Maintenance release:

* updated OS and software versions.
* it is recommended to get the sample config with `cse sample` command, update the existing `config.yaml` with the changes and re-create the templates.
* added NFS Persistent volume support.

**Usibility Improvements and Bug Fixes:**
* VCD 8.20 requires pyvcloud 19.3.0 and vcd_cli 20.3.0 versions.

---

## CSE 1.0.0

Release date: 2018-03-09

| VCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS | 17.12.0-ce | 1.9.3      | Weave 2.1.3 |

CSE General Availability (GA), improvements and bug fixes:

* updated dependencies.
* fixed template preparation issues related to open-vm-tools update.
* removed unnecessary file downloads.

---

## CSE 0.4.2

Release date: 2018-02-15

| VCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS | 17.12.0-ce | 1.9.3      | Weave 2.1.3 |

Maintenance release, improvements and bug fixes:

* support for latest Kubernetes 1.9.3 in Ubuntu template.
* improved guest password configuration. It is recommended to set new password in the templates in `config.yaml` and re-create the templates.
* this version of the PhotonOS template doesn't upgrade the OS to the latest version, since there is a problem with the latest version of `open-vm-tools`.
* fixed issue while preparing Ubuntu template.
* updated license files.
* improved installation and validation of the AMQP settings.

---

## CSE 0.4.1

Release date: 2018-02-05

Maintenance release, improvements and bug fixes:

* guest password is now set using guest operations instead of using guest customization, so it is not visible in the vapp customization section; it is recommended to set new password in the templates of `config.yaml` and re-create the templates.
* fixed issue with Ubuntu template when resizing disk.
* fixed issue listing nodes.

---

## CSE 0.4.0

Release date: 2018-01-26

| VCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS | 17.12.0-ce | 1.9.1      | Weave 2.1.3 |

New features:

* support multiple vCenters per VCD installation (new format of the `vcs` section in `config.yaml`)
* upgraded PhotonOS template to version 2.0
* upgraded Ubuntu template to Kubernetes 1.9.1
* support templates from versions `0.2.0` and up, but re-creating the templates is recommended
* scripts now upgrade the OS during the creation of the template
* added `--update` template option to `cse install`

---

## CSE 0.3.0

Release date: 2018-01-10

| VCD         | OS                   | Docker     | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS   | 17.09.0-ce | 1.8.2      | Weave 2.0.5 |

New features:

* added `node {create|list|delete}` commands
* added `system {info|enable|disable|stop}` commands
* support templates from versions `0.2.0` and up

---

## CSE 0.2.0

Release date: 2017-12-29

| VCD         | OS                   | Docker     | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS   | 17.09.0-ce | 1.8.2      | Weave 2.0.5 |

New features:

* new bootstrap method
* customization as external scripts
* improved visibility of the customization process
* customize CPU, memory, ssh-key and storage-profile during cluster creation
* single vApp cluster
* multiple templates support, added list templates command
* separate client SDK and commands from pyvcloud and vcd-cli
* fully automated installation process
* improved task information

---

## CSE 0.1.2

Release date: 2017-11-10

| VCD         | OS                   | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 1.7.7      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS   | 1.8.2      | Weave 2.0.5 |

Features:

* added Ubuntu template

---

## CSE 0.1.1

Release date: 2017-10-03

| VCD         | OS                   | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 1.7.7      | Weave 2.0.4 |

Features:

* initial release
* create and delete clusters
