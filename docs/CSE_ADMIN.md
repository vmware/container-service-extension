---
layout: default
title: Overview
---
# CSE Server Management

<a name="compatibility"></a>
## CSE/vCD Compatibility

| CSE version | vCD version         |
|-------------|---------------------|
| 1.1.0       | 8.20, 9.0, 9.1      |
| 1.2.0       | 8.20, 9.0, 9.1, 9.5 |

---

<a name="privileges"></a>
## Service Account

It is recommended to create a vCD service account for CSE minimizes
required privileges. An attacker getting credentials for a user
account with admin-level privileges can be catastrophic. 

The following list shows the minimum set of rights required by a
service account to install and operate CSE.  This is subject to
change in new vCD versions.

- Catalog: CLSP Publish Subscribe
- Catalog: Create / Delete a Catalog
- Catalog: Edit Properties
- Catalog: Import Media from vSphere
- Catalog: Publish
- Catalog: Sharing
- Catalog: View ACL
- Catalog: View Private and Shared Catalogs
- Catalog: View Published Catalogs
- Cell Configuration: View
- Disk: Change Owner
- Disk: Create
- Disk: Delete
- Disk: Edit Properties
- Disk: View Properties
- General: Administrator View
- General: View Error Details
- Host: View
- Organization Default Settings: View default settings for new Organizations.
- Organization Network: Open in vSphere
- Organization Network: View
- Organization vDC Network: View Properties
- Organization vDC Resource Pool: Open in vSphere
- Organization vDC Resource Pool: View
- Organization vDC Storage Policy: Open in vSphere
- Organization vDC: Extended View
- Organization vDC: View
- Organization vDC: View ACL
- Organization: View
- System Operations: Execute System Operations
- Task: Resume, Abort, or Fail
- Task: Update
- VAPP_VM_METADATA_TO_VCENTER
- VDC Template: Instantiate
- VDC Template: View
- vApp Template / Media: Copy
- vApp Template / Media: Create / Upload
- vApp Template / Media: Edit
- vApp Template / Media: View
- vApp Template: Checkout
- vApp Template: Download
- vApp Template: Import
- vApp Template: Open in vSphere
- vApp: Allow All Extra Config
- vApp: Allow Ethernet Coalescing Extra Config
- vApp: Allow Latency Extra Config
- vApp: Allow Matching Extra Config
- vApp: Allow NUMA Node Affinity Extra Config
- vApp: Change Owner
- vApp: Copy
- vApp: Create / Reconfigure
- vApp: Delete
- vApp: Download
- vApp: Edit Properties
- vApp: Edit VM CPU
- vApp: Edit VM CPU and Memory reservation settings in all VDC types
- vApp: Edit VM Hard Disk
- vApp: Edit VM Memory
- vApp: Edit VM Network
- vApp: Edit VM Properties
- vApp: Enter/Exit Maintenance Mode
- vApp: Import Options
- vApp: Manage VM Password Settings
- vApp: Open in vSphere
- vApp: Power Operations
- vApp: Shadow VM View
- vApp: Sharing
- vApp: Snapshot Operations
- vApp: Upload
- vApp: Use Console
- vApp: VM Boot Options
- vApp: VM Check Compliance
- vApp: VM Migrate, Force Undeploy, Relocate, Consolidate
- vApp: View ACL
- vApp: View VM metrics
- vCenter: Open in vSphere
- vCenter: Refresh
- vCenter: View

Always ensure vCD service account has enough privileges. Alternatively,
you can create a role with Admin privileges and deselect/delete
rights which are not required.

<a name="configfile"></a>
## Server Config File
The CSE server is controlled by a yaml configuration file.  You can generate
a skeleton file as follows. 
```sh
> cse sample > config.yaml
```

Edit this file to add values from your vCloud Director installation.

The config file has 5 sections: `amqp`, `vcd`, `vcs`, `service`,
and `broker`.  The following sub-sections explain configuration
properties for each section.

### **amqp** section
CSE Server will communicate with vCD using these settings

During CSE Server installation, CSE can configure vCD's AMQP settings
to match these settings

`vcd` section has the following properties:

| Property          | Value                                                                                           |
|:------------------|:------------------------------------------------------------------------------------------------|
| host            | IP or hostname of the vCloud Director                                                           |
| username        | Username of the vCD service account with minimum roles and rights                               |
| password        | Password of the vCD service account.                                                             |

### **vcs** section
Guest Operations Privileges required for vCenter service account:
- Guest Operation Program Execution
- Guest Operation Modifications
- Guest Operation Queries

Each `vc` under `vcs` section has the following properties:

| Property          | Value                                                                                           |
|:------------------|:------------------------------------------------------------------------------------------------|
| name            | Name of the vCenter registered in vCD                                                                           |
| username        | Username of the vCenter service account with minimum of guest-operation privileges.             |
| password        | Password of the vCenter service account.                                                        |

### **service** section
Specify how many threads you want CSE Server to create.

### **broker** section
`broker` section has the following properties:

| Property           | Value                                                                                                                                                                                                                |
|:--------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| type               | Broker type, set to `default`                                                                                                                                                                                        |
| org                | vCD organization that contains the shared catalog where the master templates will be stored                                                                                                                          |
| vdc                | Virtual datacenter within `org` that will be used during the install process to build the template                                                                                                                   |
| network            | Org Network within `vdc` that will be used during the install process to build the template. It should have outbound access to the public Internet. The `CSE` appliance doesn't need to be connected to this network |
| ip_allocation_mode | IP allocation mode to be used during the install process to build the template. Possible values are `dhcp` or `pool`. During creation of clusters for tenants, `pool` IP allocation mode is always used              |
| catalog            | Public shared catalog within `org` where the template will be published                                                                                                                                              |
| cse_msg_dir        | Reserved for future use                                                                                                                                                                                              |
| storage_profile    | Name of the storage profile to use when creating the temporary vApp used to build the template                                                                                                                       |
| default_template   | Name of the default template to use if none is specified                                                                                                                                                             |
| templates          | A list of templates available for clusters                                                                                                                                                                           |

Each `template` in the `templates` property has the following properties:

| Property          | Value                                                                                                                                                                                                             |
|:------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name            | Unique name of the template                                                                                                                                                                                       |
| source_ova      | URL of the source OVA to download                                                                                                                                                                                 |
| sha256_ova        | sha256 of the source OVA                                                                                                                                                                                            |
| source_ova_name | Name of the source OVA in the catalog                                                                                                                                                                             |
| catalog_item    | Name of the template in the catalog                                                                                                                                                                               |
| description     | Information about the template                                                                                                                                                                                    |
| temp_vapp       | Name of the temporary vApp used to build the template. Once the template is created, this vApp can be deleted. It will be deleted by default during the installation based on the value of the `cleanup` property |
| cleanup         | If `True`, `temp_vapp` will be deleted by the install process after the master template is created                                                                                                                |
| admin_password  | `root` password for the template and instantiated VMs. This password should not be shared with tenants                                                                                                            |
| cpu             | Number of virtual CPUs to be allocated for each VM                                                                                                                                                                |
| mem             | Memory in MB to be allocated for each VM                                                                                                                                                                          |

---

<a name="vmtemplates"></a>
## VM Templates
`CSE` supports multiple VM templates to create Kubernetes clusters from. Templates may vary in guest OS or software versions, and must have a unique name. One template must be defined as the default template, and tenants have the option to specify the template to use during cluster/node creation.

### **Source .ova Files for VM Templates**

| OS                   | OVA Name                               | URL                                                                                                       | SHA256                                                           |
|----------------------|----------------------------------------|-----------------------------------------------------------------------------------------------------------|------------------------------------------------------------------|
| Photon OS 1.0, Rev 2 | photon-custom-hw11-1.0-62c543d.ova     | `https://bintray.com/vmware/photon/download_file?file_path=photon-custom-hw11-1.0-62c543d.ova`            | 6d6024c5531f5554bb0d2f51f3005078ce6d4ee63c142f2453a416824c5344ca |
| Photon OS 2.0 GA     | photon-custom-hw11-2.0-304b817.ova     | `http://dl.bintray.com/vmware/photon/2.0/GA/ova/photon-custom-hw11-2.0-304b817.ova`                       | cb51e4b6d899c3588f961e73282709a0d054bb421787e140a1d80c24d4fd89e1 |
| Ubuntu 16.04.4 LTS   | ubuntu-16.04-server-cloudimg-amd64.ova | `https://cloud-images.ubuntu.com/releases/xenial/release-20180418/ubuntu-16.04-server-cloudimg-amd64.ova` | 3c1bec8e2770af5b9b0462e20b7b24633666feedff43c099a6fb1330fcc869a9 |

### **Updating VM Templates**
CSE Server should be gracefully stopped before updating VM templates, to avoid errors that can occur when using `vcd cse cluster create ...` or `vcd cse node create ...`

In general, updating a template doesn't have any effect on existing Kubernetes master and worker nodes. CSE and template compatibility can be found in release notes.

Templates can also be generated on a vCD instance that CSE Server is not registered to. Templates can be generated in multiple vCD instances in parallel.

Update a template:
```sh
> cse install -c config.yaml --template photon-v2 --update --amqp skip --ext skip
```

Updating a template increases `versionNumber` of the corresponding catalog item by 1:
```sh
> vcd catalog info cse photon-custom-hw11-2.0-304b817-k8s
```
---

<a name="serversetup"></a>
## Server Setup

### Installing CSE Server

`CSE` Server should be installed by the vCloud Director System/Cloud
Administrator on a new VM or one of the existing servers that are
part of vCD. This CSE VM is the **CSE appliance**.

The CSE appliance requires network access to the vCD cell, vCenter(s),
and AMQP server. It does not require access to the network(s) where
the Kubernetes templates will be created (`network` and `temp_vapp`
config file properties) or the tenant network(s) where the clusters
will be created.

You should install the CSE software on the CSE appliance as described
in [Software Installation](/INSTALLATION.html).  Once this is done
you can invoke server setup using the `cse install` command.  The
following diagram illustrates the steps visually:

![cse-install](img/cse-install-2.png)

The `cse install` command supports the following options:

| Option       | Short | Argument(s)              | Description                                                                                                                                                | Default Value                                 |
|:--------------|:-------|:--------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------|
| --config     | -c    | path/to/config.yaml      | Config file to use                                                                                                                                         | config.yaml                                   |
| --template   | -t    | template-name            | Install the specified template                                                                                                                             | '*' (installs all templates specified in config file) |
| --update     | -u    | n/a                      | Recreate templates during installation                                                                                                                     | False                                         |
| --no-capture | -n    | n/a                      | Don't capture the temporary vApp as a template   (Leaves it standing for debugging purposes)                                                               | False                                         |
| --ssh-key    | -k    | path/to/ssh-key.pub      | ssh-key file to use for vm access   (root password ssh access is disabled for security reasons)                                                            | None                                          |
| --amqp       | -a    | prompt OR skip OR config | **prompt**: ask before configuring AMQP settings<br>**skip**: do not configure AMQP settings<br>**config**: configure AMQP without asking for confirmation | prompt                                        |
| --ext        | -e    | prompt OR skip OR config | **prompt**: ask before registering CSE<br>**skip**: do not register CSE<br>**config**: register CSE without asking for confirmation                        | prompt                                        |


To monitor the vApp customization process, you can ssh into the temporary vApp. In the temporary vApp, the output of the customization script is captured in `/tmp/FILENAME.out` as well as `/tmp/FILENAME.err`:
```sh
# print out file contents as it's being written to
> tail -f /tmp/FILENAME.out
> tail -f /tmp/FILENAME.err
```

The temporary vApp guest OS does not allow root ssh access via password for security reasons (use `--ssh-key` option to provide a public key).

To inspect the temporary vApp after customization, use the `--no-capture` option (also requires the `--ssh-key` option):
```sh
> cse install -c config.yaml --no-capture --ssh-key ~/.ssh/id_rsa.pub
```

### Validate CSE Installation
Validate that CSE has installed correctly with:

```sh
> cse check --config config.yaml --check-install
```
The `cse check` command supports the following options:

| Option          | Short | Argument(s)         | Description                                                           | Default                                                 |
|-----------------|-------|---------------------|-----------------------------------------------------------------------|---------------------------------------------------------|
| --config        | -c    | path/to/config.yaml | Config file to use                                                    | config.yaml                                             |
| --check-install | -i    | n/a                 | Check CSE installation on vCD                                         | False                                                   |
| --template      | -t    | template-name       | If `--check-install` is set, check that the specified template exists | '*' (checks for all templates specified in config file) |

Validate that CSE has been registered in vCD
Using `vcd-cli`, check that the extension has been registered in vCD:

```sh
# login as system administrator
> vcd login vcd.serviceprovider.com System administrator --password passw0rd -w -i

# list extensions
> vcd system extension list

# get details of CSE extension
> vcd system extension info cse
```

#### Optional
Configure the API extension timeout (seconds) on the vCloud Director cell:
```sh
> cd /opt/vmware/vcloud-director/bin
> ./cell-management-tool manage-config -n extensibility.timeout -l
> ./cell-management-tool manage-config -n extensibility.timeout -v 20
```

Manually register CSE api extension to vCD:
```sh
> vcd system extension create cse cse cse vcdext '/api/cse, /api/cse/.*, /api/cse/.*/.*'
```
---
<a name="serveroperation"></a>
## Server Operation
`CSE` Server uses threads to process requests. The number of AMQP listener threads can be configured in the config file with `listeners` property under `service` section (default is 5).

### Running CSE Server Manually
```sh
> cse run --config config.yaml

# run server in the background
> nohup cse run --config config.yaml > nohup.out 2>&1 &
```
Server output log can be found in `cse.log`

### Running CSE Server as a Service
A sample `systemd` unit is provided by CSE. Copy file `cse.service` from where CSE is installed to, and move it to `/etc/systemd/system/cse.service`. A sample `cse.sh` is also provided. (what does cse.sh does and is it used in this?)

CSE service daemon should be started using `systemctl start cse`. To enable, disable, and stop CSE service, use CSE client.
```sh
# hook CSE unit into relevant places to automatically do things
# depending on what's specified in the unit file
> vcd cse system enable

# start CSE service now
> systemctl start cse

# stop processing new requests, and finish processing existing requests
# disables CSE service
> vcd cse system disable
property    value
----------  -------
message     Updated

# wait until all active threads have finished, then exits CSE service
> vcd cse system stop -y
property    value
----------  ---------------------------------------------------------------------
message     CSE graceful shutdown started. CSE will finish processing 4 requests.

> vcd cse system info
property              value
--------------------  ------------------------------------------------------
all_threads           8
config_file           /Users/pgomez/vmware/cse/testbed-202-34.yaml
consumer_threads      5
description           Container Service Extension for VMware vCloud Director
product               CSE
python                3.6.4
requests_in_progress  4
status                Shutting down
version               1.2.0
```

If CSE Server is disabled, users will get the following message when executing any CSE command:

```bash
$ vcd cse cluster list
Usage: vcd cse cluster list [OPTIONS]

Error: CSE service is disabled. Contact the System Administrator.
```

### Monitoring CSE Service
vCD System Administrator can monitor CSE service status via CSE client:
```sh
> vcd cse system info
property              value
--------------------  ------------------------------------------------------
all_threads           10
config_file           /opt/vmware/cse/testbed-202-34.yaml
consumer_threads      6
description           Container Service Extension for VMware vCloud Director
product               CSE
python                3.6.4
requests_in_progress  3
status                Running
version               1.2.0
```

On Photon OS, to keep the service running after logout, check `/etc/systemd/logind.conf` and set `KillUserProcesses` to `no`
```
[Login]
KillUserProcesses=no
```

System administrators can list all the clusters running in vCD with a search command using cluster vApp metadata:
```bash
> vcd search adminvapp -f 'metadata:cse.cluster.id!=STRING:'
```
---

<a name="serverupgrade"></a>
## Server Upgrade and Removal
When upgrading CSE versions, re-register the extension:
```sh
# remove previous registration of CSE
> vcd system extension delete cse

# run cse installation again
> cse install --config config.yaml
```

### Updating CSE Server Software
- Gracefully stop CSE Server
- Reinstall `container-service-extension` from PyPI:
```bash
pip3 install --user --upgrade container-service-extension
```
- Check the release notes at the end of this document for version compatibility:
- Review the configuration file for any new options introduced or deprecated in the new version
- If the previously generated templates are not longer supported by the new version, delete the templates and re-generate new ones.
- If running CSE as a service, start the new version of the service with `systemctl start cse`

### Uninstalling CSE Server
- Gracefully stop CSE Server
- As System Administrator, unregister CSE from vCD:
```sh
> vcd system extension delete cse
```
- Review vCD AMQP settings. May not require any modifications
```shell
> vcd system amqp info
```
- (Optional) Delete VM templates and the CSE catalog from vCD

---
<a name="commandssysadmin"></a>
## Useful Commands
`cse ...` commands are used by system administrators to:
- Install CSE Server
- Create/update templates
- Run CSE Server manually

`vcd cse ...` commands are used by system administrators to:
- Monitor status of CSE Server and clusters
- Operate CSE as a service

```sh
### Use '-h' option to see help page and options for any command
> cse install --config config.yaml
> cse check --config config.yaml
> cse run --config config.yaml

# login to vCD to use vcd-cli commands
> vcd login IP system USERNAME -iwp PASSWORD

# set ORGNAME to be active org for this session
> vcd org use ORGNAME

# set VDCNAME to be active vdc for this session
> vcd vdc use VDCNAME
```
