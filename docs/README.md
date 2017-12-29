The **container-service-extension** (`CSE`) is an add-on to VMware vCloud Director that helps tenants work with Kubernetes clusters.

## Overview

`CSE` enables Kubernetes as a service on vCloud Director (vCD) installations. `CSE` is based on VM templates that are automatically generated during the installation process, or anytime thereafter. vCD tenants can then request fully functional Kubernetes clusters that `CSE` instantiate on the tenant VDC from the templates, customized based on the tenant preferences.

The current document covers the following `CSE` topics:
  - installation
  - configuration
  - usage

## Installation

The `CSE` service is designed to be installed by the vCloud Director System Administrator on a virtual machine (the `CSE` appliance) with access to the vCD cell, AMQP server and vCenter server.

vCD tenants can use `CSE` through [vcd-cli](https://vmware.github.io/vcd-cli). Web UI access will be available in a future release.

### System Administrator Installation

Allocate a new virtual machine to run `CSE` (the `CSE` appliance) or use one of the existing servers in the vCloud Director installation. `CSE` requires Python 3.6 or higher. See the appendix at the end for installing Python 3 on different platforms.

The `CSE` appliance doesn't need access to the network where the master template will be created (`network` and `temp_vapp` configuration parameters) or the tenant networks where the clusters will be created. The `CSE` appliance requires network access to the vCD cell, AMQP server and vCenter server.

#### 1. Install `CSE` package.

```shell
$ pip3 install container-service-extension

$ cse version
Container Service Extension for VMware vCloud Director, version 0.2.0
```
The exact version might be different from the one listed above.

`CSE` can also be installed using [virtualenv](https://virtualenv.pypa.io) and [virtualenvwrapper](http://virtualenvwrapper.readthedocs.io). `pip3 install` can be used with additional parameters depending on the needs:

| parameter | meaning |
|-----------|---------|
|`--user`   | install to the Python user install directory |
| `--upgrade` | upgrade an existing installation |
| `--pre`   | install a pre-release and development version |
| `--no-cache-dir` | disable the cache and download the package |

#### 2. Generate a skeleton configuration and provide site specific settings.

```shell
$ cse sample > config.yaml
```

Edit file `config.yaml` with the values for your vCloud Director installation. The following table describes the setting values.

##### `CSE` Configuration Settings

`CSE` supports multiple templates to create Kubernetes clusters. Each template might have a different guest OS or Kubernetes versions, and must have an unique name. One template has to be defined as the default. Tenants can specify the template to use during cluster creation, or use the default.

The configuration file has 5 sections:
  - `amqp`: AMQP settings
  - `vcd`: vCD settings
  - `vcs`: vCenter Server settings
  - `service`: service settings
  - `broker`: service broker settings

|Group|Property|Value|
|-----|--------|-----|
|`broker`|||
||`type`|Broker type, set to `default`|
||`org`|vCD organization that contains the shared catalog where the master templates will be stored|
||`vdc`|Virtual datacenter within `org` that will be used during the install process to build the template|
||`network`|Org Network within `vdc` that will be used during the install process to build the template. It should have outbound access to the public Internet. The `CSE` appliance doesn't need to be connected to this network|
||`ip_allocation_mode`|IP allocation mode to be used during the install process to build the template. Possible values are `dhcp` or `pool`. During creation of clusters for tenants, `pool` IP allocation mode is always used|
||`catalog`|Public shared catalog within `org` where the template will be published|
||`cse_msg_dir`|Reserved for future use|
||`storage_profile`|Name of the storage profile to use when creating the temporary vApp used to build the template|
||`default_template`|Name of the default template to use if none is specified|
||`templates`| A list of templates available for clusters|

Each `template` in the `templates` property of `broker` has the following properties:

|Property|Value|
|--------|-----|
|`name`|Unique name of the template|
|`source_ova`|URL of the source OVA to download|
|`sha1_ova`|sha1 of the source OVA|
|`source_ova_name`|Name of the source OVA in the catalog|
|`catalog_item`|Name of the template in the catalog|
|`description`|Information about the template|
|`temp_vapp`|Name of the temporary vApp used to build the template. Once the template is created, this vApp can be deleted. It will be deleted by default during the installation based on the value of the `cleanup` property|
|`cleanup`|If `True`, `temp_vapp` will be deleted by the install process after the master template is created|
|`admin_password`|`root` password for the template and instantiated VMs. This password should not be shared with tenants|
|`cpu`|Number of virtual CPUs to be allocated for each VM|
|`mem`|Memory in MB to be allocated for each VM|


#### 3. Install the extension.

The installation will take a few minutes to complete. Use the command below:

```shell
$ cse install --config config.yaml
```

The `install` command will generate the templates required to run the service and will configure the vCD settings defined in the configuration file.

To inspect the `temp_vapp` vApp, it is possible to pass the `--no-capture` option:

```shell
$ cse install --config config.yaml --no-capture
```

With `--no-capture`, the install process will create the `temp_vapp` vApp, will keep it running and not capture it as a template. This allows to `ssh` into the vApp and inspect it. The output of the customization process is captured by the `install` command.

The generated password of `temp_vapp` guest OS can be retrieved with:

```shell
$ vcd vapp info temp_vapp | grep password
```

If you need to delete a template to generate a new one, use `vcd-cli`:

```shell
$ vcd catalog delete <catalog> <catalog-item>
```

Optionally, configure the API extension timeout (seconds) on the vCloud Director cell:

```shell
cd /opt/vmware/vcloud-director/bin
./cell-management-tool manage-config -n extensibility.timeout -l
./cell-management-tool manage-config -n extensibility.timeout -v 20
```

#### 4. Validate configuration.

Validate the configuration with:

```shell
$ cse check --config config.yaml

```

#### 5. Start `CSE`

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

### Tenant Installation

vCloud Director tenants use `CSE` through [vcd-cli](https://vmware.github.io/vcd-cli), which is included in `CSE`. Tenants will need to install the `CSE` package via pip3:

```shell
$ pip3 install container-service-extension

$ vcd version
vcd-cli, VMware vCloud Director Command Line Interface, 20.0.0
```
The exact version might be different from the one listed above.

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
$ vcd cse
Usage: vcd cse [OPTIONS] COMMAND [ARGS]...

  Work with kubernetes clusters in vCloud Director.

    Examples
        vcd cse cluster list
            Get list of kubernetes clusters in current virtual datacenter.
        ...
```

## Using the Container Service

Once installed, `CSE` can be used by tenants to create kubernetes clusters on demand, using `vcd-cli`. See [vcd-cli](https://vmware.github.io/vcd-cli) for more information about all the available commands.

The virtual machines (master and nodes) will be provisioned on the tenant virtual datacenter within a vApp. The VMs will be connected to the network specified with the `--network` required parameter. The network should be configured with a static IP pool and it doesn't require access to the Internet (access might be required if installing additional components).

The `CSE` service doesn't need a network connection to the tenant virtual datacenters.

Below are some usage examples:

```shell
# create cluster mycluster with one master and two nodes, connected to provided network
# a public key is provided to be able to ssh into the VMs
$ vcd cse cluster create mycluster --network intranet --ssh-key ~/.ssh/id_rsa.pub

# list the VMs of the cluster
$ vcd vapp list mycluster

# create cluster mycluster with one master, three nodes and connected to provided network
$ vcd cse cluster create mycluster --network intranet --nodes 3 --ssh-key ~/.ssh/id_rsa.pub

# create a single node cluster, connected to provided network
$ vcd cse cluster create mycluster --network intranet --nodes 0 --ssh-key ~/.ssh/id_rsa.pub

# list available clusters
$ vcd cse cluster list

# retrieve cluster config
$ vcd cluster config mycluster > ~/.kube/config

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
$ vcd cse cluster delete mycluster
```
## Reference

### Command syntax

```shell
$ vcd cse
Usage: vcd cse [OPTIONS] COMMAND [ARGS]...

  Work with kubernetes clusters in vCloud Director.

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

          vcd cse template list
              Get list of CSE templates available.


Options:
  -h, --help  Show this message and exit.

Commands:
  cluster   work with clusters
  template  manage CSE templates
```

```shell
$ vcd cse cluster
Usage: vcd cse cluster [OPTIONS] COMMAND [ARGS]...

  Work with kubernetes clusters.

Options:
  -h, --help  Show this message and exit.

Commands:
  add-node     add node
  config       get cluster config
  create       create cluster
  delete       delete cluster
  list         list clusters
```

```shell
$ cse
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

          cse install
              Install CSE.

          cse install --template photon-v1
              Install CSE. It only creates the template specified.

          cse install --template photon-v1 --no-capture
              Install CSE. It only creates the temporary vApp specified in the
              config file. It will not capture the vApp in the catalog.

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
  check      check configuration
  install    install CSE on vCD
  run        run service
  sample     generate sample configuration
  uninstall  uninstall CSE from vCD
  version    show version
```

### Versions

#### CSE 0.2.0

Release date: 2017-12-29

|vCD|OS                  |Docker    |Kubernetes|Pod Network|
|---|--------------------|----------|----------|-----------|
|9.0|Photon OS 1.0, Rev 2|17.06.0-ce|1.8.1     |Weave 2.0.5|
|9.0|Ubuntu 16.04.3 LTS  |17.09.0-ce|1.8.2     |Weave 2.0.5|

#### CSE 0.1.2

Release date: 2017-11-10

|vCD|OS                  |Kubernetes|Pod Network|
|---|--------------------|----------|-----------|
|9.0|Photon OS 1.0, Rev 2|1.7.7     |Weave 2.0.5|
|9.0|Ubuntu 16.04.3 LTS  |1.8.2     |Weave 2.0.5|

#### CSE 0.1.1

Release date: 2017-10-03

|vCD|OS                  |Kubernetes|Pod Network|
|---|--------------------|----------|-----------|
|9.0|Photon OS 1.0, Rev 2|1.7.7     |Weave 2.0.4|

### Source OVA Files

|OS                  |OVA Name| URL    |SHA1      |
|--------------------|--------|--------|----------|
|Photon OS 1.0, Rev 2|photon-custom-hw11-1.0-62c543d.ova |`https://bintray.com/vmware/photon/download_file?file_path=photon-custom-hw11-1.0-62c543d.ova`|18c1a6d31545b757d897c61a0c3cc0e54d8aeeba|
|Ubuntu 16.04.3 LTS|ubuntu-16.04-server-cloudimg-amd64.ova|`https://cloud-images.ubuntu.com/releases/xenial/release-20171011/ubuntu-16.04-server-cloudimg-amd64.ova`|1bddf68820c717e13c6d1acd800fb7b4d197b411|

### Installation Details

#### Installing Python 3 and CSE on Photon OS

Photon OS 2.0 RC:

```shell
$ sudo tdnf install -y build-essential python3-setuptools python3-tools python3-pip
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

#### Installing Python 3 on macOS

Install using [Homebrew](https://brew.sh):

```shell
$ brew install python3
```

#### Installing Python 3.6 on Centos 7

```shell
$ sudo yum update
$ sudo yum install -y yum-utils
$ sudo yum groupinstall -y development
$ sudo yum -y install https://centos7.iuscommunity.org/ius-release.rpm
$ sudo yum -y install python36u python36u-pip python36u-devel
$ sudo easy_install-3.6 pip
```

#### Installing Python 3 on Ubuntu 16.04

```shell
$ sudo apt install python3-pip
```
