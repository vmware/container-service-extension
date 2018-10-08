# __**CSE Release Notes**__
[back to main CSE page](README.md#releasenotes)
### CSE 1.1.0

Release date: 2018-04-20

| vCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.4-ce | 1.9.1      | Weave 2.3.0 |
| 8.10 and up | Ubuntu 16.04.4 LTS | 18.03.0-ce | 1.10.1     | Weave 2.3.0 |

Maintenance release:
- updated OS and software versions.
- it is recommended to get the sample config with `cse sample` command, update the existing `config.yaml` with the changes and re-create the templates.
- added NFS Persistent volume support.


### CSE 1.0.0
Release date: 2018-03-09

| vCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS | 17.12.0-ce | 1.9.3      | Weave 2.1.3 |

CSE General Availability (GA), improvements and bug fixes:
- updated dependencies.
- fixed template preparation issues related to open-vm-tools update.
- removed unnecessary file downloads.

### CSE 0.4.2

Release date: 2018-02-15

| vCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS | 17.12.0-ce | 1.9.3      | Weave 2.1.3 |

Maintenance release, improvements and bug fixes:
- support for latest Kubernetes 1.9.3 in Ubuntu template.
- improved guest password configuration. It is recommended to set new password in the templates in `config.yaml` and re-create the templates.
- this version of the PhotonOS template doesn't upgrade the OS to the latest version, since there is a problem with the latest version of `open-vm-tools`.
- fixed issue while preparing Ubuntu template.
- updated license files.
- improved installation and validation of the AMQP settings.

### CSE 0.4.1

Release date: 2018-02-05

Maintenance release, improvements and bug fixes:
- guest password is now set using guest operations instead of using guest customization, so it is not visible in the vapp customization section; it is recommended to set new password in the templates of `config.yaml` and re-create the templates.
- fixed issue with Ubuntu template when resizing disk.
- fixed issue listing nodes.

### CSE 0.4.0

Release date: 2018-01-26

| vCD         | OS                 | Docker     | Kubernetes | Pod Network |
|:------------|:-------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 2.0 GA   | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS | 17.12.0-ce | 1.9.1      | Weave 2.1.3 |

New features:
- support multiple vCenters per vCD installation (new format of the `vcs` section in `config.yaml`)
- upgraded PhotonOS template to version 2.0
- upgraded Ubuntu template to Kubernetes 1.9.1
- support templates from versions `0.2.0` and up, but re-creating the templates is recommended
- scripts now upgrade the OS during the creation of the template
- added `--update` template option to `cse install`

### CSE 0.3.0

Release date: 2018-01-10

| vCD         | OS                   | Docker     | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS   | 17.09.0-ce | 1.8.2      | Weave 2.0.5 |

New features:
- added `node {create|list|delete}` commands
- added `system {info|enable|disable|stop}` commands
- support templates from versions `0.2.0` and up

### CSE 0.2.0

Release date: 2017-12-29

| vCD         | OS                   | Docker     | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 17.06.0-ce | 1.8.1      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS   | 17.09.0-ce | 1.8.2      | Weave 2.0.5 |

New features:
- new bootstrap method
- customization as external scripts
- improved visibility of the customization process
- customize CPU, memory, ssh-key and storage-profile during cluster creation
- single vApp cluster
- multiple templates support, added list templates command
- separate client SDK and commands from pyvcloud and vcd-cli
- fully automated installation process
- improved task information

### CSE 0.1.2

Release date: 2017-11-10

| vCD         | OS                   | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 1.7.7      | Weave 2.0.5 |
| 8.10 and up | Ubuntu 16.04.3 LTS   | 1.8.2      | Weave 2.0.5 |

Features:
- added Ubuntu template

### CSE 0.1.1

Release date: 2017-10-03

| vCD         | OS                   | Kubernetes | Pod Network |
|:------------|:---------------------|:-----------|:------------|
| 8.10 and up | Photon OS 1.0, Rev 2 | 1.7.7      | Weave 2.0.4 |

Features:
- initial release
- create and delete clusters