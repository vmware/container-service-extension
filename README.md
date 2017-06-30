

# container-service-extension

## Overview

The *container-service-extension* is a vCloud Director extension that manages the life cycle of Kubernetes clusters on behalf of the tenants.

## Try it out

### Prerequisites

This extension should be installed on a vCloud Director instance by a system administrator.

The *container-service-extension* is a Python package and requires Python 2.7.

### Install & Run

Installation:

``` shell
pip install --user container-service-extension
cse init
```
Edit file `config.yml` and provide the values for your vCloud Director installation.

Start the service with:

``` shell
cse run config.yml
```

### Development

``` shell
git clone https://github.com/vmware/container-service-extension.git
cd container-service-extension
python setup.py develop
cse init
#edit config.yml
cse run config.yml
```

## Documentation

[wiki](https://github.com/vmware/container-service-extension/wiki).

## Contributing

The *container-service-extension* project team welcomes contributions from the community. If you wish to contribute code and you have not
signed our contributor license agreement (CLA), our bot will update the issue when you open a Pull Request. For any
questions about the CLA process, please refer to our [FAQ](https://cla.vmware.com/faq). For more detailed information,
refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[BSD-2](LICENSE.txt)
