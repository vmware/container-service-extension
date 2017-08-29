# container-service-extension

[![asciicast](https://asciinema.org/a/135505.png)](https://asciinema.org/a/135505)

## Overview

The **container-service-extension** for vCloud Director manages the life cycle of Kubernetes clusters for tenants.

## Try it out

### Prerequisites

This extension should be installed on a vCloud Director instance by a system administrator.

The **container-service-extension** is distributed as a Python package.

### Install & Run

#### Installation:

Install and validate:

``` shell
$ pip install --user container-service-extension

$ cse version
```

#### Running the Service

Follow the vCloud Director configuration steps in the [wiki](https://github.com/vmware/container-service-extension/wiki).

Start the service with:

``` shell
$ cse run config.yml
```

More information about `vcd-cli` commands to use the service can be found in the [wiki](https://github.com/vmware/vcd-cli/wiki/container-service-extension).

### Development

``` shell
$ git clone https://github.com/vmware/container-service-extension.git
$ python setup.py develop
```

## Documentation

See our [wiki](https://github.com/vmware/container-service-extension/wiki).

## Contributing

The *container-service-extension* project team welcomes contributions from the community. Before you start working with *container-service-extension*, please read our [Developer Certificate of Origin](https://cla.vmware.com/dco). All contributions to this repository must be signed as described on that page. Your signature certifies that you wrote the patch or have the right to pass it on as an open-source patch. For more detailed information, refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[BSD-2](LICENSE.txt)
