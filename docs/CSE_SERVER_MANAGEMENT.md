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

```sh
cse install -c config.yaml --ssh-key ~/.ssh/id_rsa.pub
```

Please find more details on how to generate sample config file and populate it correctly, [here](/container-service-extension/CSE_CONFIG.html).

The following diagram illustrates installation steps visually.

![cse-install](img/cse-server-installation.png)

The `cse install` command supports the following options:

| Option                    | Short | Argument(s)                        | Description                                                                                                      | Default Value |
|---------------------------|-------|------------------------------------|------------------------------------------------------------------------------------------------------------------|---------------|
| \--config                 | -c    | path to config file                | Filepath of CSE config file to use for installation                                                              | config.yaml   |
| \--force-update           | -f    | n/a                                | Recreate CSE k8s templates on vCD even if they already exist                                                     | False         |
| \--pks-config-file        | -p    | path to Enterprise PKS config file | Filepath of Enterprise PKS config file to use for installation                                                   | -             |
| \--retain-temp-vapp       | -d    | n/a                                | Retain the temporary vApp after the template has been captured --ssh-key option is required if this flag is used | False         |
| \--skip-config-decryption | -s    | n/a                                | Skips decrypting the configuration file and pks configuration file, and assumes them to be plain text            | -             |
| \--skip-template-creation | -t    | n/a                                | Skips creating CSE k8s template during installation                                                              | False         |
| \--ssh-key                | -k    | path to public ssh key file        | ssh-key file to use for VM access (root password ssh access is disabled for security reasons)                    | -             |

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
cse check config.yaml --check-install
```

The validity and integrity of just the CSE config file can be checked using the
following command.
```sh
cse check config.yaml
cse check config.yaml --pks-config-file pks.yaml
```

The `cse check` command supports the following options:

| Option                    | Short | Argument(s)                        | Description                                                                                           | Default |
|---------------------------|-------|------------------------------------|-------------------------------------------------------------------------------------------------------|---------|
| \--check-install          | -i    | n/a                                | Check CSE installation on vCD                                                                         | False   |
| \--pks-config-file        | -p    | path to Enterprise PKS config file | Enterprise PKS config file to validate along with CSE config file                                     | -       |
| \--skip-config-decryption | -s    | n/a                                | Skips decrypting the configuration file and PKS configuration file, and assumes them to be plain text | -       |

Validate that CSE has been registered with vCD as an extension, via vcd-cli:
```sh
# login as system administrator
vcd login vcd.serviceprovider.com system <administrator user name> --password <password> -w -i

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
users across all organizations who has the right `Catalog: View Published Catalogs`.
Users with `Organization Administrator` role, already has this right baked into their role.
However if users who are not organization administrator want to access this catalog
(cluster creation requires access to this catalog), they need to be assigned a role
that has the above mentioned right. The following set of commands can be used to
achieve the desired outcome.

```sh
# login as system administrator
vcd login vcd.serviceprovider.com system administrator --password passw0rd -w -i

# switch over to the tenant organization
vcd org use myorg

# add the right to the role of the user in question
vcd role add-right <role name> 'Catalog: View Published Catalogs'

# built-in roles can't be edited and needs to be cloned first
vcd role clone <built role e.g. "vApp Author"> 'New Role'
vcd role add-right 'New Role' 'Catalog: View Published Catalogs'

# Assign this new role to the user in question via vCD UI or
# create a new user in the organization with the new role
vcd user create <new user name> <password> 'New Role' --enabled
```

---

<a name="server_operation"></a>

## Server Operation

The CSE Server uses threads to process requests. The number of AMQP
listener threads can be configured in the config file using the `listeners`
property in the `service` section. The default value is 10.

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

Once installed you can start the CSE service daemon using `systemctl start cse`.
To enable, disable, and stop the CSE service remotely, use CSE client.

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

```sh
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
all_threads           11
config_file           config_2_6_0.yaml
consumer_threads      10
description           Container Service Extension for VMware vCloud Director
product               CSE
python                3.7.4
requests_in_progress  0
status                Running
version               2.6.0
```
---

<a name="server_upgrade"></a>

## Server Upgrade and Removal

Upgrading CSE server is no different than installing it for the first time.


### Upgrading CSE Server Software

1. Gracefully stop CSE Server.
2. Reinstall `container-service-extension` from PyPI:
   * `pip3 install --user --upgrade container-service-extension`
3. Check the [release notes](/container-service-extension/RELEASE_NOTES.html) for version compatibility.
4. Use `cse sample` command to generate a new sample config file and fill in
   the relevant values from the previous config file.
5. If the previously generated templates are no longer supported by the new version,
   delete the old templates (from vCD UI / vcd-cli) and generate new ones via
   * `cse install -c myconfig.yaml`
   Check [here](/container-service-extension/TEMPLATE_ANNOUNCEMENTS.html) for available templates.
6. If CSE is being run as a service, start the new version of the service with
   * `systemctl start cse`.

### Uninstalling CSE Server

1. Gracefully stop CSE Server
2. As System Administrator, unregister CSE from vCD:
   * `vcd system extension delete cse`
3. Review vCD AMQP settings. Generally no modifications are necessary in AMQP.
   * `vcd system amqp info`
4. (Optional) Delete Kubernetes templates and the CSE catalog from vCD.

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
cse check config.yaml -h
cse run --config config.yaml -h

# Show all available vcd cse commands.
vcd cse -h

# Login to vCD to use vcd-cli commands.
vcd login <vCD HOSTNAME> system <USERNAME> -iwp <PASSWORD>

# Let SAMPLE_ORG_NAME be active org for this session.
vcd org use SAMPLE_ORG_NAME

# Let SAMPLE_VDC_NAME be active vdc for this session.
vcd vdc use SAMPLE_VDC_NAME

# Enable organization vdc for a particular K8s provider (Native/Enterprise PKS)
vcd cse ovdc enable SAMPLE_VDC_NAME --k8s-provider [native|ent-pks]
```
