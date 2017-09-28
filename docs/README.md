The **container-service-extension** is a vCloud Director add-on that manages the life cycle of Kubernetes clusters for tenants.

## Service Provider Installation

The installation process includes the following steps to be completed as the vCloud Director system administrator:

1. download and install the `CSE` software package
2. create vApp templates and upload to vCloud Director
4. register the `CSE` service extension with vCloud Director
5. edit and validate `CSE` configuration settings
6. start `CSE`

vCloud Director tenants just need to:

- install `vcd-cli` and `kubectl` on their client computer
- start using `CSE` and `kubernetes`

### 1. Package Installation

Allocate a new virtual machine to run `CSE` or use one of the existing servers in the vCloud Director installation. Install the `CSE` package:

```shell
$ pip install --user container-service-extension

$ cse version
```

Update an existing installation:

``` shell
$ pip install --user container-service-extension --upgrade --no-cache
```

To install the latest development version:

``` shell
$ pip install --user container-service-extension --upgrade --pre --no-cache
```

### 2. Create and Upload Templates to vCloud Director


### 3. Register `CSE` with vCloud Director
#### 3.1 Configure vCloud Director AMQP Settings

Using `vcd-cli`, configure AMQP. Log in as the system administrator:

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

API extension timeout:

```shell
cd /opt/vmware/vcloud-director/bin
./cell-management-tool manage-config -n extensibility.timeout -l
./cell-management-tool manage-config -n extensibility.timeout -v 20
```

#### 3.2 Complete vCloud Director Configuration

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

### 4. Define the `CSE` Configuration

Create sample configuration:

```shell
$ cse sample-config > config.yml
```

Edit file `config.yml` and provide the values for your vCloud Director installation.

Validate the configuration:

```shell
$ cse check config.yml

Connection to AMQP server (amqp.vmware.com:5672): success
Connection to vCloud Director as system administrator (vcd.vmware.com:443): success
Find catalog 'cse': success
Find master template 'k8s-u.ova': success
Find node template 'k8s-u.ova': success
Connection to vCenter Server as administrator@vsphere.local (vcenter.vmware.com:443): success
The configuration is valid.
```

### 5. Start `CSE`

Start the service with the command below. Output log is appended to file `cse.log`

```shell
$ cse run config.yml
```

## Using the Container Service

Once installed, the container service extension can be used by tenants to create kubernetes clusters on demand.

See [vcd-cli](https://vmware.github.io/vcd-cli/vcd_cluster) for more information about the available commands.

```shell
# create cluster c1 with one master and two nodes
$ vcd cluster create c1

# list available clusters
$ vcd cluster list

# retrieve cluster config
$ vcd cluster config c1 > ~/kubeconfig.yml

# check cluster configuration
$ export KUBECONFIG=~/kubeconfig.yml

$ kubectl get nodes

# deploy kubernetes dashboard
$ kubectl create -f https://git.io/kube-dashboard

$ kubectl proxy &

$ open http://127.0.0.1:8001/ui

# delete cluster when no longer needed
$ vcd cluster delete c1
```
