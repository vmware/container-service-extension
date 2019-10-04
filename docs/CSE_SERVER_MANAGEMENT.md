---
layout: default
title: CSE Server Management
---
# CSE Server Management

<a name="overview"></a>

## Overview

This page contains procedures to install and manage Container Service
Extension (CSE) on vCloud Director (vCD). Users who perform these procedures
are cloud administrators with `sysadmin` access and a solid understanding
of vCD management.

Procedures on this page make regular use of vcd-cli commands to
perform administrative operations. Please refer to the [vcd-cli
documentation](https://vmware.github.io/vcd-cli/) if necessary to familiarize
yourself with vcd-cli.


<a name="server_setup"></a>

## Server Setup

### Installing CSE Server

`CSE` Server should be installed by the vCD System/Cloud Administrator on a
new VM or one of the existing servers that are part of vCD. This CSE VM is the
**CSE appliance**.

The CSE appliance requires network access to the vCD cell, vCenter(s),
and AMQP server. It does not require access to the network(s) that powers the
org VDC where the Kubernetes templates will be created nor the tenant network(s)
that powers that org VDC where the clusters will be deployed. Please find more
details on the vCD prerequisites for CSE installation [here](/container-service-extension/CSE_INSTALL_PREREQUISITES.html).

The CSE software should be installed on the CSE appliance as described [here](/container-service-extension/INSTALLATION.html).

Next, CSE server setup should be invoked via the `cse install` command.
The example below shows a typical invocation.

```bash
cse install -c config.yaml --ssh-key ~/.ssh/id_rsa.pub
```

Please find more details on how to generate sample config file and populate it correctly, [here](/container-service-extension/CSE_CONFIG.html).

The following diagram illustrates installation steps visually.

![cse-install](img/cse-server-installation.png)

The `cse install` command supports the following options:

| Option | Short | Argument(s) | Description | Default Value |
|-|-|-|-|-|
| \--config | -c | path to config file | Filepath of CSE config file to use for installation | config.yaml |
| \--force-update | -f | n/a | Recreate CSE k8s templates on vCD even if they already exist | False |
| \--retain-temp-vapp | -d | n/a | Retain the temporary vApp after the template has been captured --ssh-key option is required if this flag is used | False |
| \--skip-template-creation | -s | n/a | Skips creating CSE k8s template during installation | False |
| \--ssh-key | -k    | path to public ssh key file | ssh-key file to use for VM access (root password ssh access is disabled for security reasons) | None |

To monitor the vApp customization process, we can ssh into the temporary vApp.
In the temporary vApp, the output of the customization script is captured in
`/tmp/FILENAME.out` as well as `/tmp/FILENAME.err`:

```sh
# print out file contents as it's being written to
tail -f /tmp/FILENAME.out
tail -f /tmp/FILENAME.err
```

### Validate CSE Installation

To validate that CSE server has been installed correctly, use the command
`cse check`.

```sh
cse check --config config.yaml --check-install
```

The validity of a CSE config file can also be checked using this command.
```sh
cse check --config config.yaml
```

The `cse check` command supports the following options:

| Option          | Short | Argument(s)         | Description                                                           | Default                                                 |
|-----------------|-------|---------------------|-----------------------------------------------------------------------|---------------------------------------------------------|
| --config        | -c    | path to config file | Config file to use                                                    | config.yaml                                             |
| --check-install | -i    | n/a                 | Check CSE installation on vCD                                         | False                                                   |

Validate that CSE has been registered with vCD as an extension, via vcd-cli:
```sh
# login as system administrator
vcd login vcd.serviceprovider.com System administrator --password passw0rd -w -i

# list extensions
vcd system extension list

# get details of CSE extension
vcd system extension info cse
```
<a name="extension-timeout"></a>
### Setting the API Extension Timeout

The API extension timeout is the duration (in seconds) that vCD waits for
a response from the CSE server extension. The default value is 10 seconds,
which may be too short for some environments. To alter the timeout value,
follow the steps below.

Configure the API extension timeout on the vCD cell:

```sh
cd /opt/vmware/vcloud-director/bin
./cell-management-tool manage-config -n extensibility.timeout -l
./cell-management-tool manage-config -n extensibility.timeout -v 20
```

### Manual CSE API Registration

If there is a need to re-register the CSE API extension for any reason, the
following command can be used. It might be required to delete the extension
first for this command to work.

```sh
vcd system extension create cse cse cse vcdext '/api/cse, /api/cse/.*, /api/cse/.*/.*'
```

### Sharing CSE catalog with non admin tenant users

CSE installation creates a catalog to store all the Kubernetes templates that are later
used to deploy Kubernetes clusters. This catalog is by default shared with all
organization administrators. However if users who are not organization
administrator want to access this catalog (cluster creation requires access to
this catalog), the catalog needs to be explicitly shared with each individual
organization by System administrators. The following commands can be run by a System
administrator to do so,

```sh
# login as system administrator
vcd login vcd.serviceprovider.com system administrator --password passw0rd -w -i

# switch over to the organization holding the catalog viz. cse-org
vcd org use cse-org

# share the catalog viz. cse-cat with the non org admin users in the org holding the catalog
vcd catalog acl add cse-cat 'org:cse-org:ReadOnly'

# share the catalog cse-cat to a second organization viz. test-org
vcd catalog acl add cse-cat 'org:test-org:ReadOnly'
```

---

<a name="server_operation"></a>

## Server Operation

The CSE Server uses threads to process requests. The number of AMQP
listener threads can be configured in the config file using the `listeners`
property in the `service` section. The default value is 5.

### Running CSE Server Manually

To start the manually run the command shown below.

```sh
# Run server in foreground.
cse run --config config.yaml

# Run server in background
nohup cse run --config config.yaml > nohup.out 2>&1 &
```

Server output log can be found in `cse-server-debug.log` and `cse-server-info.log`
under the folder `cse-logs`. If wire logs are truned on via config file, another file
viz. `cse-server-wire-debug.log` will also show up under the log folder.

### Running CSE Server as a Service

A sample `systemd` unit is provided by CSE. Here are instructions for
installation.

* Copy file `cse.service` from CSE installation location and move it to `/etc/systemd/system/cse.service`.
* Copy `cse.sh` to /home/vmware.

Once installed you can start the CSE service daemon using `systemctl
start cse`. To enable, disable, and stop the CSE service, use CSE client.

```sh
# hook CSE unit into relevant places to automatically do things
# depending on what's specified in the unit file
$ vcd cse system enable

# start CSE service now
$ systemctl start cse

# stop processing new requests, and finish processing existing requests
# disables CSE service
$ vcd cse system disable
property    value
----------  ----------------------
message     CSE has been disabled.

# wait until all active threads have finished, then exits CSE service
$ vcd cse system stop -y
property    value
----------  ------------------------------
message     CSE graceful shutdown started.
```

If the CSE Server is disabled, users will get the following message
when executing any CSE command:

```bash
$ vcd cse cluster list
Usage: vcd cse cluster list

Error: CSE service is disabled. Contact the System Administrator.
```

To keep the service running after logout on Photon OS, check
`/etc/systemd/logind.conf` and set `KillUserProcesses` to `no`

```sh
[Login]
KillUserProcesses=no
```

### Monitoring CSE

vCD System Administrators can monitor CSE service status via CSE client:

```sh
$ vcd cse system info
property              value
--------------------  ------------------------------------------------------
all_threads           6
config_file           config.yaml
consumer_threads      5
description           Container Service Extension for VMware vCloud Director
product               CSE
python                3.7.4
requests_in_progress  0
status                Running
version               2.5.0
```
---

<a name="server_upgrade"></a>

## Server Upgrade and Removal

Upgrading CSE server is no different than installing it for the first time.


### Upgrading CSE Server Software

1. Gracefully stop CSE Server.
2. Reinstall `container-service-extension` from PyPI:
   * `pip3 install --user --upgrade container-service-extension`
3. Check the release notes at the end of this document for version compatibility.
4. Review the configuration file for any new options introduced or deprecated in the new version.
5. `cse sample` command should be used to generate a new sample config file.
5. If the previously generated templates are no longer supported by the new version, delete the old templates (from vCD UI / vcd-cli) and generate new ones via
   * `cse install -c myconfig.yaml`
6. If CSE is being run as a service, start the new version of the service with `systemctl start cse`.

### Uninstalling CSE Server

1. Gracefully stop CSE Server
1. As System Administrator, unregister CSE from vCD:
   * `vcd system extension delete cse`
1. Review vCD AMQP settings. Generally no modifications are necessary in AMQP.
   * `vcd system amqp info`
1. (Optional) Delete Kubernetes templates and the CSE catalog from vCD.

---

<a name="commands_sys_admin"></a>

## Useful Commands

`cse ...` commands are used by system administrators to:

* Install CSE Server
* Create/Update templates
* Run CSE Server manually

`vcd cse ...` commands are used by system administrators to:

* Monitor status of CSE Server and clusters
* Operate CSE as a service
* Enable a given organization vdc for either Native or Enterprise PKS deployments.
This command is necessary only when more than one K8s provider exists in the system

The following show useful sample commands.

```sh
# Use '-h' option to see help page and options for any cse command.
cse -h
cse install --config config.yaml -h
cse check --config config.yaml -h
cse run --config config.yaml -h

# Show all available vcd cse commands.
vcd cse -h

# Login to vCD to use vcd-cli commands.
vcd login IP system USERNAME -iwp PASSWORD

# Let ORGNAME be active org for this session.
vcd org use ORGNAME

# Let VDCNAME be active vdc for this session.
vcd vdc use VDCNAME

# Enable organization vdc for a particular K8s provider (Native/Enterprise PKS)
vcd cse ovdc enable VDCNAME --k8s-provider [native|ent-pks]
```
