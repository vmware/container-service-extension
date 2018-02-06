The **container-service-extension** (`CSE`) is an add-on to VMware vCloud Director that helps tenants work with Kubernetes clusters.

# Overview

`CSE` enables Kubernetes as a service on vCloud Director (vCD) installations. `CSE` is based on VM templates that are automatically generated during the installation process, or anytime thereafter. vCD tenants can then request fully functional Kubernetes clusters that `CSE` instantiate on the tenant VDC from the templates, customized based on the tenant preferences.

The current document covers the following `CSE` topics:

- for System Administrators:
  - [installation and configuration](#installation)
  - [operation](#operation)
- for Tenants:
  - [installation](#tenant-installation)
  - [usage](#using-the-container-service)
  - [programming](#scripting-and-programming)
- [reference](#reference)
  - [command syntax](#command-syntax)
  - [release notes](#release-notes)


# Installation

The `CSE` service is designed to be installed by the vCloud Director System Administrator on a virtual machine (the `CSE` appliance) with network connectivity to the vCloud Director infrastructure where the following components access is required:

- vCloud Director instance (Public Load Balancer VIP for multiple cells)
- vCenter Server
- AMQP Server

vCD tenants can use `CSE` through [vcd-cli](https://vmware.github.io/vcd-cli). Web UI access will be available in a future release.

## System Administrator Installation

Allocate a new virtual machine to run `CSE` (the `CSE` appliance) or use one of the existing servers in the vCloud Director installation. `CSE` requires Python 3.6 or higher. See the [Appendix](#appendix) at the end for installing Python 3 on different platforms.

The `CSE` appliance doesn't need access to the network where the master template will be created (`network` and `temp_vapp` configuration parameters) or the tenant networks where the clusters will be created. The `CSE` appliance requires network access to the vCD cell, AMQP server and vCenter server.

### 1\. Install `CSE` package.

```shell
$ pip3 install --user container-service-extension

$ cse version
CSE, Container Service Extension for VMware vCloud Director, version 0.3.0
```

Alternatively, `CSE` can be installed directly from GitHub specifying a version number with:

```shell
$ pip3 install --user git+https://github.com/vmware/container-service-extension.git@0.3.0
```

The exact version might be different from the one listed above.

`CSE` can also be installed using [virtualenv](https://virtualenv.pypa.io) and [virtualenvwrapper](http://virtualenvwrapper.readthedocs.io). `pip3 install` can be used with additional options depending on the needs:

| option           | meaning                                       |
|:-----------------|:----------------------------------------------|
| `--user`         | install to the Python user install directory  |
| `--upgrade`      | upgrade an existing installation              |
| `--pre`          | install a pre-release and development version |
| `--no-cache-dir` | disable the cache and download the package    |

### 2\. Generate a skeleton configuration and provide site specific settings.

```shell
$ cse sample > config.yaml
```

Edit file `config.yaml` with the values for your vCloud Director installation. The following table describes the setting values.

#### `CSE` Configuration Settings

`CSE` supports multiple templates to create Kubernetes clusters. Each template might have a different guest OS or Kubernetes versions, and must have an unique name. One template has to be defined as the default. Tenants can specify the template to use during cluster or node creation, or use the default.

The configuration file has 5 sections:

- `amqp`: AMQP settings
- `vcd`: vCD settings
- `vcs`: vCenter Server settings
- `service`: service settings
- `broker`: service broker settings

| Group                | Property                                                                                                                                                                                                             | Value |
|:---------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------|
| `broker`             |                                                                                                                                                                                                                      |       |
| `type`               | Broker type, set to `default`                                                                                                                                                                                        |       |
| `org`                | vCD organization that contains the shared catalog where the master templates will be stored                                                                                                                          |       |
| `vdc`                | Virtual datacenter within `org` that will be used during the install process to build the template                                                                                                                   |       |
| `network`            | Org Network within `vdc` that will be used during the install process to build the template. It should have outbound access to the public Internet. The `CSE` appliance doesn't need to be connected to this network |       |
| `ip_allocation_mode` | IP allocation mode to be used during the install process to build the template. Possible values are `dhcp` or `pool`. During creation of clusters for tenants, `pool` IP allocation mode is always used              |       |
| `catalog`            | Public shared catalog within `org` where the template will be published                                                                                                                                              |       |
| `cse_msg_dir`        | Reserved for future use                                                                                                                                                                                              |       |
| `storage_profile`    | Name of the storage profile to use when creating the temporary vApp used to build the template                                                                                                                       |       |
| `default_template`   | Name of the default template to use if none is specified                                                                                                                                                             |       |
| `templates`          | A list of templates available for clusters                                                                                                                                                                           |       |

Each `template` in the `templates` property of `broker` has the following properties:

| Property          | Value                                                                                                                                                                                                             |
|:------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `name`            | Unique name of the template                                                                                                                                                                                       |
| `source_ova`      | URL of the source OVA to download                                                                                                                                                                                 |
| `sha1_ova`        | sha1 of the source OVA                                                                                                                                                                                            |
| `source_ova_name` | Name of the source OVA in the catalog                                                                                                                                                                             |
| `catalog_item`    | Name of the template in the catalog                                                                                                                                                                               |
| `description`     | Information about the template                                                                                                                                                                                    |
| `temp_vapp`       | Name of the temporary vApp used to build the template. Once the template is created, this vApp can be deleted. It will be deleted by default during the installation based on the value of the `cleanup` property |
| `cleanup`         | If `True`, `temp_vapp` will be deleted by the install process after the master template is created                                                                                                                |
| `admin_password`  | `root` password for the template and instantiated VMs. This password should not be shared with tenants                                                                                                            |
| `cpu`             | Number of virtual CPUs to be allocated for each VM                                                                                                                                                                |
| `mem`             | Memory in MB to be allocated for each VM                                                                                                                                                                          |

### 3\. Install the extension.

The installation will take a few minutes to complete. Use the command below:

```shell
$ cse install --config config.yaml
```

The `install` command will generate the templates required to run the service and will configure the vCD settings defined in the configuration file. The output of the customization process is captured by the `install` command and displayed at the end of the process.

To monitor the progress during the creation, it is possible to ssh into the `temp_vapp` while the script is being executed. In the `temp_vapp`, the output of the customization script is being captured in a file in the `/tmp` directory and can be monitored with `tail -f /tmp/<file-name>.out`. The standard error is captured in a file with extension `.err` in the `/tmp` directory.

The generated password of `temp_vapp` guest OS can be retrieved with:

```shell
$ vcd vapp info temp_vapp | grep password
```

To inspect the `temp_vapp` vApp, it is possible to pass the `--no-capture` option:

```shell
$ cse install --config config.yaml --no-capture
```

With `--no-capture`, the install process will create the `temp_vapp` vApp, will keep it running and not capture it as a template. This allows to `ssh` into the vApp and inspect it.

If you need to delete a template to generate a new one, use `vcd-cli`:

```shell
$ vcd catalog delete <catalog> <catalog-item>
```

The `cse install` command supports the following options:

| option                   | meaning                                                 |
|:-------------------------|:--------------------------------------------------------|
| `--config <config-file>` | Config file to use.                                     |
| `--template <template>`  | Install the specified template.                         |
| `--update`               | Update and overwrite the templates                      |
| `--no-capture`           | Customize `temp_vapp` but not capture it as a template. |
| `--amqp prompt`          | Ask before configuring AMQP (default).                  |
| `--amqp skip`            | Do not configure AMQP settings.                         |
| `--amqp config`          | Configure AMQP without asking for confirmation.         |
| `--ext prompt`           | Ask before registering CSE as an extension (default).   |
| `--ext skip`             | Do not register CSE as an extension.                    |
| `--ext config`           | Register CSE as an extension asking for confirmation.   |

Optionally, configure the API extension timeout (seconds) on the vCloud Director cell:

```shell
cd /opt/vmware/vcloud-director/bin
./cell-management-tool manage-config -n extensibility.timeout -l
./cell-management-tool manage-config -n extensibility.timeout -v 20
```

### 4\. Validate configuration.

Validate the configuration with:

```shell
$ cse check --config config.yaml
```

Using `vcd-cli`, check that the extension has been registered in vCD:

```shell
# login as system administrator
$ vcd login vcd.serviceprovider.com System administrator --password passw0rd -w -i

# list extensions
vcd system extension list

# get details of CSE extension
vcd system extension info cse
```

Alternatively, the `CSE` api extension can be manually registered with a `vcd-cli` command as follows:

```shell
$ vcd system extension create cse cse cse vcdext '/api/cse, /api/cse/.*, /api/cse/.*/.*'
```

When upgrading from versions previous to `0.2.0`, re-register the extension:

```shell
# remove previous registration of CSE
$ vcd system extension delete cse -y

# run the install process to register CSE again
cse install --config config.yaml
```

The `cse check` command supports the following options:

| option                   | meaning                          |
|:-------------------------|:---------------------------------|
| `--config <config-file>` | Config file to use.              |
| `--template <template>`  | Validate the specified template. |

### 5\. Start `CSE`

Start the service with the command below. Output log is appended to file `cse.log`

```shell
$ cse run --config config.yaml
```

To run it in the background:

```shell
$ nohup cse run --config config.yaml > nohup.out 2>&1 &
```

On Photon OS, check file `/etc/systemd/logind.conf` and make sure `KillUserProcesses` is set to 'no' to keep the service running after login out.

```
[Login]
KillUserProcesses=no
```

A sample `systemd` unit is provided. Customize and copy file `cse.service` in the repository to `/etc/systemd/system/cse.service`. A sample `cse.sh` is also provided.

Install with:

```
systemctl enable cse
```

Start with:

```
systemctl start cse
```

## Operation

### Starting and Stopping

The preferred method to start `CSE` is by configuring a `systemd` unit. Once installed, `CSE` can be started with `systemctl start cse`. In version `0.3.0` we are introducing a new command to monitor and operate the `CSE` service (`vcd cse system`). A `vCD` System Administrator can monitor the status of `CSE` with:

```bash
$ vcd cse system info
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
version               0.3.0
```

`CSE` service can be `disabled` to stop processing new requests. Existing in-flight requests will continue processing until they finish. If `CSE` is disabled, users will get the following message when executing any `CSE` command:

```bash
$ vcd cse cluster list
Usage: vcd cse cluster list [OPTIONS]

Error: CSE service is disabled. Contact the System Administrator.
```

`CSE` service can be `enabled` by the `vCD` System Administrator with the command: `vcd cse system enable`.

The preferred method to stop `CSE` is through the `vcd cse system` command, to ensure that no new requests can be processed and in-flight requests can finish before stoping the service. Using directly `systemctl` is not recommended since that would interrupt requests that might be in progress.

To stop `CSE` gracefully, first disable the service with the `vcd cse system disable` command and then stop it with the `vcd cse system stop` command. Once the `stop` command is issued, `CSE` will wait until all the active requests are completed and then it will exit. The status of `CSE` can be monitored during shutdown. `CSE` can't be re-enabled again while it is shutting down, use `systemctl start cse` to re-start `CSE` again after it finished.

Here is an example of the shutdown sequence:

```bash
$ vcd cse system disable
property    value
----------  -------
message     Updated

$ vcd cse system stop -y
property    value
----------  ---------------------------------------------------------------------
message     CSE graceful shutdown started. CSE will finish processing 4 requests.

$ vcd cse system info
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
version               0.3.0
```

### Monitoring

Tenants can list their own clusters with the `vcd cse cluster list`. System administrators can list all the clusters running in the system with a search command using the metadata in the cluster vApp. Here is an example:

```bash
$ vcd search adminvapp -f 'metadata:cse.cluster.id!=STRING:'
id                                    isDeployed    isEnabled      memoryAllocationMB  name        numberOfCpus    numberOfVMs  ownerName    status        storageKB  vdcName
------------------------------------  ------------  -----------  --------------------  --------  --------------  -------------  -----------  ----------  -----------  -------
ca3ba2d6-4a97-42f4-8fa8-dff7c9bff88d  true          true                         6144  cluster1               6              3  tenant1      POWERED_ON     50331648  vdc1
fa879527-c4e1-4955-a8d1-ca4de377b553  true          true                         6144  cluster2               6              3  tenant2      POWERED_ON     50331648  vcd2
81ef3214-db6e-4341-b0c5-9f44aea1da26  true          true                         6144  cluster3               6              3  tenant2      POWERED_ON     50331648  vdc2

```

### Tuning

`CSE` service uses threads to process requests. The number of AMQP listener threads can be configured in the `config.yaml` with the `listeners` property under the `service` section. The default value is `5` threads.

### Upgrading

The process to upgrade `CSE` to the latest version involves the following steps:
- gracefully stop `CSE` service
- install the new version of the `container-service-extension` module. Use the command below.
- check the release notes at the end of this document for version compatibility:
  - review the configuration file for any new options introduced or deprecated in the new version
  - if the previously generated templates are not longer supported by the new version, delete the templates and re-generate new ones.
- start the new version of the service with `systemctl start cse`

Upgrade command:
```bash
pip3 install --user --upgrade container-service-extension
```

### Updating Templates

The templates used by `CSE` can be updated at any time. The `CSE` service should be gracefully stopped before updating templates. When creating (or updating) a template, new upgrades to the OS are installed in the template, therefore it is recommended to perform template updates on a regular basis. During instantiation of the templates as master or worker nodes, the software on the instantiated VM is the original software installed in the template and is not upgraded.

In general, updating a template doesn't have any effect on existing kubernetes master and worker nodes. The release notes provides information about compatibility between versions of `CSE` and templates.

Follow these steps to update a template:

- stop the `CSE` service
- update the desired template, for example:

```shell
$ cse install --config config.yaml --template photon-v2 --update --amqp skip --ext skip
```

Once a template has been updated, the `versionNumber` of the corresponding catalog item will be increased by one. The `versionNumber` can be checked with the `vcd catalog info` command, for example:

```shell
$ vcd catalog info cse photon-custom-hw11-2.0-304b817-k8s
```

- start the `CSE` service

### Adding New Templates

Documentation on how to add new templates will be provided soon.

### Uninstalling

`CSE` can be uninstalled from a vCloud Director instance following these steps:

- stop the `CSE` service
- unregister the `cse` API extension. As a System Administrator run:

```shell
$ vcd system extension delete cse
```

- review the `AMQP Broker` settings. It might not require any modification if there are other API extensions installed in the system.

```shell
$ vcd system amqp info
```

- optionally, delete the templates and the shared catalog if the templates won't be used.

## Tenant Installation

vCloud Director tenants use `CSE` through [vcd-cli](https://vmware.github.io/vcd-cli), which is included in `CSE`. Tenants will need to install the `CSE` package via pip3:

```shell
$ pip3 install --user container-service-extension

$ vcd version
vcd-cli, VMware vCloud Director Command Line Interface, 20.0.0
```

The exact versions might be different from the ones listed above.

After the install, edit `~/.vcd-cli/profiles.yaml` and add the following two lines between the `active` and `profiles` entries:

`~/.vcd-cli/profiles.yaml` before changes:

```yaml
active: default
profiles:
```

after changes:

```yaml
active: default
extensions:
- container_service_extension.client.cse
profiles:
```

Validate the new commands are installed with:

```shell
$ vcd cse version
CSE, Container Service Extension for VMware vCloud Director, version 0.3.0
```

The exact version might be different from the one listed above.

# Using the Container Service

Once installed, `CSE` can be used by tenants to create kubernetes clusters on demand, using `vcd-cli`. See [vcd-cli](https://vmware.github.io/vcd-cli) for more information about all the available commands.

The virtual machines (master and nodes) will be provisioned on the tenant virtual datacenter within a vApp. The VMs will be connected to the network specified with the `--network` required parameter. The Organization VDC network should have a static IP pool and it doesn't require access to the Internet (access might be required if installing additional components).

When creating clusters and nodes, the `--network` option is required, as they need a network to operate and no network will be selected by default if omitted.

The `CSE` service doesn't need a network connection to the tenant virtual datacenters.

When creating a cluster, the tenant can specify the template to use for the master and nodes of the cluster, as well as other options. When adding nodes to the cluster, the same type of options can be used to customize the new nodes.

Here is a summary of the commands available to manage templates, clusters and nodes:

| command                                           | purpose                                     |
|:--------------------------------------------------|:--------------------------------------------|
| `vcd cse template list`                           | List available templates to create clusters |
| `vcd cse cluster create <cluster-name>`           | Create a new kubernetes cluster             |
| `vcd cse cluster list`                            | List created clusters.                      |
| `vcd cse cluster delete <cluster-name>`           | Delete a kubernetes cluster.                |
| `vcd cse node create <cluster-name> --nodes n`    | Add `n` nodes to a cluster.                 |
| `vcd cse node list <cluster-name>`                | List nodes of a cluster.                    |
| `vcd cse node delete <cluster-name> [node-name]+` | Delete nodes from a cluster.                |


Most of the `CSE` operations (actions `create` and `delete`) return a task. By default, `vcd-cli` displays the progress of the task until the task finishes or fails. When using the `--no-wait` option of `vcd-cli`, the `CSE` command will return with the task information, including the task id. Use the `vcd task wait <task-id>` command to display the status and progress of the task. Another useful command is `vcd task list running` to list the current running tasks in the user's organization.

```
$ vcd --no-wait cse cluster create mycluster --network intranet --ssh-key ~/.ssh/id_rsa.pub

$ vcd task wait 377e802d-f278-44e8-9282-7ab822017cbd
```

Below are some usage examples:

```shell
# create cluster mycluster with one master and two nodes, connected to provided network
# a public key is provided to be able to ssh into the VMs
$ vcd cse cluster create mycluster --network intranet --ssh-key ~/.ssh/id_rsa.pub

# list the nodes of a cluster
$ vcd cse node list mycluster

# create cluster mycluster with one master, three nodes and connected to provided network
$ vcd cse cluster create mycluster --network intranet --nodes 3 --ssh-key ~/.ssh/id_rsa.pub

# create a single node cluster, connected to the specified network. Nodes can be added later
$ vcd cse cluster create mycluster --network intranet --nodes 0 --ssh-key ~/.ssh/id_rsa.pub

# add 2 nodes to a cluster with 4GB of ram and 4 CPUs each, from the photon-v2 template
# and using the specified storage profile
$ vcd cse node create mycluster --nodes 2 --network intranet --ssh-key ~/.ssh/id_rsa.pub \
                                --memory 4096 --cpu 4 --template photon-v2
                                --storage-profile Development

# delete 2 nodes from a cluster
$ vcd cse node delete mycluster node-dj3s node-b4rt --yes

# list available clusters
$ vcd cse cluster list

# retrieve cluster config
$ vcd cse cluster config mycluster > ~/.kube/config

# check cluster configuration
$ kubectl get nodes

# deploy a sample application
$ kubectl create namespace sock-shop

$ kubectl apply -n sock-shop -f "https://github.com/microservices-demo/microservices-demo/blob/master/deploy/kubernetes/complete-demo.yaml?raw=true"

# check that all pods are running and ready
$ kubectl get pods --namespace sock-shop

# access the application
$ IP=`vcd cse cluster list|grep '\ mycluster'|cut -f 1 -d ' '`
$ open "http://${IP}:30001"

# delete cluster when no longer needed
$ vcd cse cluster delete mycluster --yes
```

## Scripting and Programming

`CSE` can be easily scripted via `vcd-cli` commands to automate the creation and operation of kubernetes clusters and nodes. `CSE` is also available through REST API and a Python library included in the module. As an example, the following Python script creates a kubernetes cluster programmatically on vCloud Director:

```python
#!/usr/bin/env python3
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from container_service_extension.client.cluster import Cluster

client = Client('vcd.mysp.com')
client.set_credentials(BasicLoginCredentials('usr1', 'org1', '******'))

cse = Cluster(client)
result= cse.create_cluster('vdc1', 'net1', 'cluster1')
task = client.get_resource(result['task_href'])
task = client.get_task_monitor().wait_for_status(task)
print(task.get('status'))

client.logout()
```

# Reference

## Command syntax

`CSE` includes two commands:

- `cse`
  - used by the system administrator to install `CSE`, create and update templates and run the `CSE` service.
- `vcd cse`
  - used by the system administrator to operate the service:
    - get status
    - enable
    - disable
    - stop
  - used by the tenants to:
    - list templates
    - create, list and delete clusters
    - create, list and delete nodes
    - get status of the service

`CSE` also includes a `systemd` unit to:
  - enable the service in the system
  - start the service

### vcd cse

```
Usage: vcd cse [OPTIONS] COMMAND [ARGS]...

  Work with kubernetes clusters in vCloud Director.

      Description
          The cse command works with kubernetes clusters on vCloud Director.

          'vcd cse cluster create' creates a new kubernetes cluster in the
          current virtual datacenter.

          'vcd cse node create' creates new and attach new nodes to an existing
          kubernetes cluster in the current virtual datacenter.

          When creating clusters and nodes, the '--network' option is required,
          as they need a network to operate and no network will be selected by
          default if omitted.

          Cluster names should follow the syntax for valid hostnames and can have
          up to 25 characters .`system`, `template` and `swagger*` are reserved
          words and cannot be used to name a cluster.

      Examples
          vcd cse cluster list
              Get list of kubernetes clusters in current virtual datacenter.

          vcd cse cluster create dev-cluster --network net1
              Create a kubernetes cluster in current virtual datacenter.

          vcd cse cluster create prod-cluster --nodes 4 \
                      --network net1 --storage-profile '*'
              Create a kubernetes cluster with 4 worker nodes.

          vcd cse cluster delete dev-cluster
              Delete a kubernetes cluster by name.

          vcd cse cluster create c1 --nodes 0 --network net1
              Create a single node kubernetes cluster for dev/test.

          vcd cse node list c1
              List nodes in a cluster.

          vcd cse template list
              Get list of CSE templates available.

          vcd cse version
              Display version.


Options:
  -h, --help  Show this message and exit.

Commands:
  cluster   work with clusters
  node      work with nodes
  system    work with CSE service
  template  work with templates
  version   show version
```

### vcd cse template

```
Usage: vcd cse template [OPTIONS] COMMAND [ARGS]...

  Work with CSE templates.

Options:
  -h, --help  Show this message and exit.

Commands:
  list  list templates
```

### vcd cse cluster

```
Usage: vcd cse cluster [OPTIONS] COMMAND [ARGS]...

  Work with kubernetes clusters.

Options:
  -h, --help  Show this message and exit.

Commands:
  config  get cluster config
  create  create cluster
  delete  delete cluster
  info    get cluster info
  list    list clusters
```

### vcd cse cluster create
```
Usage: vcd cse cluster create [OPTIONS] NAME

Options:
  -N, --nodes INTEGER         Number of nodes to create
  -c, --cpu INTEGER           Number of virtual CPUs on each node
  -m, --memory INTEGER        Amount of memory (in MB) on each node
  -n, --network TEXT          Network name  [required]
  -s, --storage-profile TEXT  Name of the storage profile for the nodes
  -k, --ssh-key FILENAME      SSH public key to connect to the guest OS on the
                              VM
  -t, --template TEXT         Name of the template to instantiate nodes from
  -h, --help                  Show this message and exit.
```

### vcd cse node

```
Usage: vcd cse node [OPTIONS] COMMAND [ARGS]...

  Work with CSE cluster nodes.

Options:
  -h, --help  Show this message and exit.

Commands:
  create  add node(s) to cluster
  delete  delete node(s)
  list    list nodes
```

### vcd cse node create
```
Usage: vcd cse node create [OPTIONS] NAME

Options:
  -N, --nodes INTEGER         Number of nodes to create
  -c, --cpu INTEGER           Number of virtual CPUs on each node
  -m, --memory INTEGER        Amount of memory (in MB) on each node
  -n, --network TEXT          Network name  [required]
  -s, --storage-profile TEXT  Name of the storage profile for the nodes
  -k, --ssh-key FILENAME      SSH public key to connect to the guest OS on the
                              VM
  -t, --template TEXT         Name of the template to instantiate nodes from
  --type [node]               type of node to add
  -h, --help                  Show this message and exit.
  ```

### vcd cse system
```
Usage: vcd cse system [OPTIONS] COMMAND [ARGS]...

  Work with CSE service.

Options:
  -h, --help  Show this message and exit.

Commands:
  disable  disable CSE service
  enable   enable CSE service
  info     CSE system info
  stop     gracefully stop CSE service
```

### cse

```
Usage: cse [OPTIONS] COMMAND [ARGS]...

  Container Service Extension for VMware vCloud Director.

      Manages CSE.

      Examples
          cse sample
              Generate sample config.

          cse sample > config.yaml
              Save sample config.

          cse check
              Validate configuration.

          cse install --config config.yaml
              Install CSE.

          cse install --config config.yaml --template photon-v2
              Install CSE. It only creates the template specified.

          cse install --config config.yaml --template photon-v2 --no-capture
              Install CSE. It only creates the temporary vApp specified in the
              config file. It will not capture the vApp in the catalog.

          cse install --config config.yaml --template photon-v2 --update \
                      --amqp skip --ext skip
              Update the specified template.

          cse version
              Display version.

      Environment Variables
          CSE_CONFIG
              If this environment variable is set, the commands will use the file
              indicated in the variable as the config file. The file indicated
              with the '--config' option will have preference over the
              environment variable. If both are omitted, it defaults to file
              'config.yaml' in the current directory.


Options:
  -h, --help  Show this message and exit.

Commands:
  check    check configuration
  install  install CSE on vCD
  run      run service
  sample   generate sample configuration
  version  show version
```

## Release Notes

`CSE` is supported on VMware vCloud Director versions `8.10.0` and up.

### CSE 0.4.1

Release date: 2018-02-05

Maintenance release, improvements and bug fixes:
- guest password is now set using guest operations instead of using guest customization, so it is not visible in the vapp customization section; it is recommended to set new password in the templates of `config.yaml` and re-create the templates.
- fixed issue with Ubuntu template when resizing disk
- fixed issue listing nodes

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

## Source OVA Files

| OS                   | OVA Name                               | URL                                                                                                       | SHA1                                     |
|:---------------------|:---------------------------------------|:----------------------------------------------------------------------------------------------------------|:-----------------------------------------|
| Photon OS 1.0, Rev 2 | photon-custom-hw11-1.0-62c543d.ova     | `https://bintray.com/vmware/photon/download_file?file_path=photon-custom-hw11-1.0-62c543d.ova`            | 18c1a6d31545b757d897c61a0c3cc0e54d8aeeba |
| Photon OS 2.0 GA     | photon-custom-hw11-2.0-304b817.ova     | `http://dl.bintray.com/vmware/photon/2.0/GA/ova/photon-custom-hw11-2.0-304b817.ova`                       | b8c183785bbf582bcd1be7cde7c22e5758fb3f16 |
| Ubuntu 16.04.3 LTS   | ubuntu-16.04-server-cloudimg-amd64.ova | `https://cloud-images.ubuntu.com/releases/xenial/release-20171011/ubuntu-16.04-server-cloudimg-amd64.ova` | 1bddf68820c717e13c6d1acd800fb7b4d197b411 |

# Appendix

## Installation Details

### Installing Python 3 and CSE on Photon OS

Photon OS 2.0 RC:

```shell
$ sudo tdnf install -y build-essential python3-setuptools python3-tools python3-pip python3-devel
$ pip3 install --user --pre --upgrade --no-cache container-service-extension
$ export LANG=en_US.UTF-8
$ cse version
```

Photon OS 1.0, Revision 2:

```shell
$ sudo tdnf install -y gcc glibc-devel glibc-lang binutils python3-devel linux-api-headers gawk
$ sudo locale-gen.sh
$ pip3 install --user --pre --upgrade --no-cache container-service-extension
$ cse version
```

### Installing Python 3 on macOS

Install using [Homebrew](https://brew.sh):

```shell
$ brew install python3
```

### Installing Python 3.6 on Centos 7

```shell
$ sudo yum update
$ sudo yum install -y yum-utils
$ sudo yum groupinstall -y development
$ sudo yum -y install https://centos7.iuscommunity.org/ius-release.rpm
$ sudo yum -y install python36u python36u-pip python36u-devel
$ sudo easy_install-3.6 pip
```

### Installing Python 3 on Ubuntu 16.04

```shell
$ sudo apt install python3-pip
```
