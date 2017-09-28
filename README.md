# container-service-extension

[![Join the chat at https://gitter.im/container-service-extension/Lobby](https://badges.gitter.im/container-service-extension/Lobby.svg)](https://gitter.im/container-service-extension/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

[![asciicast](https://asciinema.org/a/135505.png)](https://asciinema.org/a/135505)

## Overview

The **container-service-extension** is a vCloud Director add-on that manages the life cycle of Kubernetes clusters for tenants.

## Try it out

#### Prerequisites

This extension is designed to be installed on a vCloud Director instance by the service provider (system administrator).

The **container-service-extension** is distributed as a Python package.

#### Installation:

Install and validate:

``` shell
$ pip install container-service-extension

$ cse version
```

#### Running the Service

Follow the [configuration steps](https://vmware.github.io/container-service-extension/).

Start the service with:

``` shell
$ cse run config.yml
```

More information about `vcd-cli` commands to use the service can be found in the [vcd-cli](https://vmware.github.io/vcd-cli/vcd_cluster) site.

## Development

``` shell
$ git clone https://github.com/vmware/container-service-extension.git
$ python setup.py develop
```

## Documentation

See our [site](https://vmware.github.io/container-service-extension/).

## Contributing

The *container-service-extension* project team welcomes contributions from the community. Before you start working with *container-service-extension*, please read our [Developer Certificate of Origin](https://cla.vmware.com/dco). All contributions to this repository must be signed as described on that page. Your signature certifies that you wrote the patch or have the right to pass it on as an open-source patch. For more detailed information, refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[BSD-2](LICENSE.txt)
