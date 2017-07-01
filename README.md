

# container-service-extension

## Overview

The **container-service-extension** for vCloud Director manages the life cycle of Kubernetes clusters for tenants.

## Try it out

### Prerequisites

This extension should be installed on a vCloud Director instance by a system administrator.

The **container-service-extension** is a Python package and requires Python 2.7.

### Install & Run

Installation:

``` shell
$ pip install --user container-service-extension

$ cse init
```
Edit file `config.yml` and provide the values for your vCloud Director installation.

Validate the configuration:

``` shell
$ cse check config.yml

Connection to RabbitMQ (rbmq.cpsbu.eng.vmware.com:5672): True
Connection to vCloud Director (https://vcd.eng.vmware.com:443): True
  login to 'System' org: True
```

Start the service:

``` shell
$ cse run config.yml
```

### Development

``` shell
$ git clone https://github.com/vmware/container-service-extension.git
$ cd container-service-extension
$ python setup.py develop
$ cse init
```
edit config.yml

``` shell
$ cse check config.yml
$ cse run config.yml
```

## Documentation

[wiki](https://github.com/vmware/container-service-extension/wiki).

## Contributing

The *container-service-extension* project team welcomes contributions from the community. Before you start working with *container-service-extension*, please read our [Developer Certificate of Origin](https://cla.vmware.com/dco). All contributions to this repository must be signed as described on that page. Your signature certifies that you wrote the patch or have the right to pass it on as an open-source patch. For more detailed information, refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[BSD-2](LICENSE.txt)
