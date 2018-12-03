# **CSE Release Notes**

[back to main CSE page](README.md#releasenotes)
---

## CSE 1.2.5

Release date: 2018-12-03

This is a security release to address Kubernetes CVE-2018-1002105

Supported vCD versions: 8.20, 9.0, 9.1, 9.5

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

Supported vCD versions: 8.20, 9.0, 9.1, 9.5

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
* Fixed bug where master node creation fails during cluster create command.

**Documentation:**

* Added list of minimum required user rights for a CSE Service account (#152)

---

## CSE 1.2.3

Replaced with 1.2.4 due to bug where master node creation fails during cluster create command.

---

## CSE 1.2.2

Release date: 2018-10-29

Supported vCD versions: 8.20, 9.0, 9.1, 9.5

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

Supported vCD versions: 8.20, 9.0, 9.1, 9.5

| Template OS        | Docker     | Kubernetes | Pod Network |
|:-------------------|:-----------|:-----------|:------------|
| Photon OS 2.0 GA   | 17.06.4-ce | 1.9.1      | Weave 2.3.0 |
| Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.1     | Weave 2.3.0 |

**Usability Improvements and Bug Fixes:**

* Add `status` display for `vcd cse cluster list`
* Updated pyvcloud requirement to >= 20.0.1 (#138)
* Fixed bug in setup files where CSE script files would not be downloaded properly to Windows systems from PyPI.
* Fixed bug where AMQP exchange would not be created if vCD and config file settings were the same.

**Documentation:**

* Updated CSE main documentation (#132)
* Updated docstrings (in code) for commands (#133)
* Updated help text during cluster creation

---

## CSE 1.2.0

Release date: 2018-10-02

Supported vCD versions: 8.20, 9.0, 9.1, 9.5

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

* Fixed AMQP settings display bug, where settings that were different between vCD and config file were displayed out of order.
* If current vcd settings are same as config file, AMQP configuration is skipped.
* Fixed grub issue in ubuntu customization script, where user would be prompted with a selection menu, causing installation to hang.
* CSE installation now always shares templates.
* pyvcloud, vcd-cli version requirement update

**Documentation:**

* CSE License files uploaded
* Updated known issues section
* Listed required privileges for VCD service account
* Updated CSE-vCD compatibility matrix (#109)

---

## CSE 1.1.0

Release date: 2018-04-20

| vCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.4-ce | 1.9.1      | Weave 2.3.0 |
| 8.10 and up | Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.1     | Weave 2.3.0 |

Maintenance release:

* updated OS and software versions.
* it is recommended to get the sample config with `cse sample` command, update the existing `config.yaml` with the changes and re-create the templates.
* added NFS Persistent volume support.

---

## CSE 1.0.0

Release date: 2018-03-09

| vCD         | OS                 | Docker     | Kubernetes | Pod Network |
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

| vCD         | OS                 | Docker     | Kubernetes | Pod Network |
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

| vCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS | 17.12.0-ce | 1.9.1      | Weave 2.1.3 |

New features:

* support multiple vCenters per vCD installation (new format of the `vcs` section in `config.yaml`)
* upgraded PhotonOS template to version 2.0
* upgraded Ubuntu template to Kubernetes 1.9.1
* support templates from versions `0.2.0` and up, but re-creating the templates is recommended
* scripts now upgrade the OS during the creation of the template
* added `--update` template option to `cse install`

---

## CSE 0.3.0

Release date: 2018-01-10

| vCD         | OS                   | Docker     | Kubernetes | Pod Network |
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

| vCD         | OS                   | Docker     | Kubernetes | Pod Network |
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

| vCD         | OS                   | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 1.7.7      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS   | 1.8.2      | Weave 2.0.5 |

Features:

* added Ubuntu template

---

## CSE 0.1.1

Release date: 2017-10-03

| vCD         | OS                   | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 1.7.7      | Weave 2.0.4 |

Features:

* initial release
* create and delete clusters