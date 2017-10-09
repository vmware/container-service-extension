The **container-service-extension** (`CSE`) is a VMware vCloud Director add-on that manages the life cycle of Kubernetes clusters for tenants.


## Installation

The `CSE` service is designed to be installed by the vCloud Director System Administrator on a virtual machine (the `CSE` appliance) with access to the vCD cell, AMQP server and vCenter server.

vCD tenants can use `CSE` through [vcd-cli](https://vmware.github.io/vcd-cli).

### System Administrator Installation

Allocate a new virtual machine to run `CSE` (the `CSE` appliance) or use one of the existing servers in the vCloud Director installation. `CSE` requires Python 3. See the appendix at the end for installing Python 3 on different platforms.

The `CSE` appliance doesn't need access to the network where the master template will be created (`network` and `temp_vapp` configuration parameters) or the tenant networks where the clusters will be created. The `CSE` appliance requires network access to the vCD cell, AMQP server and vCenter server.

#### 1. Install `CSE` package.

```shell
$ pip3 install container-service-extension

$ cse version
Container Service Extension for VMware vCloud Director, version 0.1.1
```

`CSE` can also be installed using [virtualenv](https://virtualenv.pypa.io) and [virtualenvwrapper](http://virtualenvwrapper.readthedocs.io). `pip3 install` can be used with additional parameters depending on the needs:

| parameter | meaning |
|-----------|---------|
|`--user`   | install to the Python user install directory |
| `--upgrade` | upgrade an existing installation |
| `--pre`   | install a pre-release and development version |
| `--no-cache-dir` | disable the cache and download the package |

#### 2. Generate a skeleton configuration and provide site specific settings.

```shell
$ cse sample-config > config.yaml
```

Edit file `config.yaml` with the values for your vCloud Director installation. The following table describes the setting values.

##### `CSE` Configuration Settings

|Group|Property|Value|
|-----|--------|-----|
|`broker`|||
||`org`|vCD organization that contains the shared catalog where the master templates will be stored|
||`vdc`|Virtual datacenter within `org` that will be used during the install process to build the template|
||`network`|Org Network within `vdc` that will be used during the install process to build the template. It should have outbound access to the public Internet. The `CSE` appliance doesn't need to be connected to this network|
||`ip_allocation_mode`|IP allocation mode to be used during the install process to build the template. Possible values are `dhcp` or `pool`. During creation of clusters for tenants, `pool` IP allocation mode is always used|
||`catalog`|Catalog within `org` where the template will be published|
||`temp_vapp`|Name of the temporary vApp used to build the template. Once the template is created, this vApp can be deleted|
||`cleanup`|If `True`, `temp_vapp` will be deleted by the install process after the master template is created|
||`password`|`root` password for the template and instantiated VMs. This password should not be shared with tenants|
||`master_cpu`|Number of virtual CPUs to be allocated for each Kubernetes master VM|
||`master_mem`|Memory in MB to be allocated for each Kubernetes master VM|
||`node_cpu`|Number of virtual CPUs to be allocated for each Kubernetes master VM|
||`node_mem`|Memory in MB to be allocated for each Kubernetes node VM|



#### 3. Install the extension.

The installation will take a few minutes. Use the command below:

```shell
$ cse install config.yaml
```

#### 4. Configure vCloud Director.

Using `vcd-cli` included with `CSE`, configure AMQP. Log in as the system administrator:

```shell
$ vcd login vcd.vmware.com System administrator --password 'p@$$w0rd'

administrator logged in, org: 'System', vdc: ''
```

Retrieve the current AMQP settings and save to a local file:

```shell
$ vcd -j system amqp info > amqp-config.json
```

Edit the `amqp-config.json` file:

```javascript
{
    "AmqpExchange": "vcdext",
    "AmqpHost": "amqp.vmware.com",
    "AmqpPort": "5672",
    "AmqpPrefix": "vcd",
    "AmqpSslAcceptAll": "false",
    "AmqpUseSSL": "false",
    "AmqpUsername": "guest",
    "AmqpVHost": "/"
}
```

Test the new AMQP configuration:

```shell
$ vcd system amqp test amqp-config.json --password guest
The configuration is valid.
```

Set the new AMQP configuration:

```shell
$ vcd system amqp set amqp-config.json --password guest
Updated AMQP configuration.
```

Using `vcd-cli`, register the extension in vCloud Director.

```shell
$ vcd system extension register cse cse cse vcdext '/api/cluster, /api/cluster/.*, /api/cluster/.*/.*'

Extension registered.
```

Check that the extension has been registered:

```shell
$ vcd system extension list

enabled    exchange    isAuthorizationEnabled    name    namespace      priority  routingKey
---------  ----------  ------------------------  ------  -----------  ----------  ------------
true       vcdext      false                     cse     cse                   0  cse
```

```shell
$  vcd system extension info cse

property                value
----------------------  ------------------------------------
enabled                 true
exchange                vcdext
id                      a5625825-d703-4f8c-b221-f41b7843979f
isAuthorizationEnabled  false
name                    cse
namespace               cse
priority                0
routingKey              cse
```

Optionally, configure the API extension timeout (seconds) on the vCloud Director cell:

```shell
cd /opt/vmware/vcloud-director/bin
./cell-management-tool manage-config -n extensibility.timeout -l
./cell-management-tool manage-config -n extensibility.timeout -v 20
```

#### 5. Start `CSE`

Start the service with the command below. Output log is appended to file `cse.log`

```shell
$ cse run config.yaml
```

To run it in the background:

```shell
$ nohup cse run config.yaml > nohup.out 2>&1 &
```

On Photon OS, check file `/etc/systemd/logind.conf` and make sure `KillUserProcesses` is set to 'no' to keep the service running after login out.

```
[Login]
KillUserProcesses=no
```

### Tenant Installation

vCloud Director tenants just need to install the [vcd-cli](https://vmware.github.io/vcd-cli) package:

```shell
$ pip3 install vcd-cli

$ vcd version
vcd-cli, VMware vCloud Director Command Line Interface, 19.2.0
```

## Using the Container Service

Once installed, the container service extension can be used by tenants to create kubernetes clusters on demand.

See [vcd-cli](https://vmware.github.io/vcd-cli/vcd_cluster) for more information about the available commands.

The virtual machines (master and nodes) will be provisioned on the tenant virtual datacenter. The VMs will be connected to the first available network or to the network specified with the `--network` optional parameter. The network should be configured with a static IP pool and it doesn't require access to the Internet.

The `CSE` service doesn't need a network connection to the tenant virtual datacenters.

```shell
# create cluster c1 with one master and two nodes
$ vcd cluster create c2

# create cluster c3 with one master, three nodes and connected to provided network
$ vcd cluster create c3 --nodes 3 --network intranet

# create a single node cluster
$ vcd cluster create c0 --nodes 0

# list available clusters
$ vcd cluster list

# retrieve cluster config
$ vcd cluster config c2 > ~/kubeconfig.yml

# check cluster configuration
$ export KUBECONFIG=~/kubeconfig.yml

$ kubectl get nodes

# deploy a sample application
$ kubectl create namespace sock-shop

$ kubectl apply -n sock-shop -f "https://github.com/microservices-demo/microservices-demo/blob/master/deploy/kubernetes/complete-demo.yaml?raw=true"

# chech that all pods are running and ready
$ kubectl get pods --namespace sock-shop

# access the application
$ IP=`vcd cluster list|grep c2|cut -f 1 -d ' '`
$ open "http://${IP}:30001"

# delete cluster when no longer needed
$ vcd cluster delete c2
```

### Versions

|Release Date|CSE|vCD|OS|Kubernetes|Pod Network|
|----------|---|---|--|----------|-----------|
|2017-10-03|0.1.1|9.0|Photon OS 1.0, Rev 2|1.7.7|Weave 2.0.4|

### Appendix

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
