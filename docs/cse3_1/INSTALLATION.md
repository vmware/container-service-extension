---
layout: default
title: Software Installation
---
# Installation

<a name="overview"></a>
## Overview

How much of CSE you need to install varies on the user type and what part
of CSE and Kubernetes you will interact with.  Here's a short table
to help decide what to install.

| User Type                         | Task(s)                                              |
|-----------------------------------|------------------------------------------------------|
| Kubernetes user                   | Install kubectl on laptop or workstation             |
| Org admin managing K8s clusters   | Install CSE and configure CSE client on laptop or VM |
| Cloud admin installing CSE in VCD | Install CSE on server host                           |

Naturally a cloud admin may install the CSE client to test cluster
creation after CSE server setup. Similarly a tenant org administrator
may install kubectl to check Kubernetes clusters or perform
administrative tasks.

<a name="kubectl"></a>
## Install Kubectl

Install kubectl using directions from the [Kubernetes web site](https://kubernetes.io/docs/tasks/tools/install-kubectl/).

<a name="getting_cse"></a>
## Install CSE Software

Install python 3.7.3+, 3.8.x, 3.9.x or 3.10.x.

See python installation instructions and downloads at <https://www.python.org> or
consult the [vcd-cli install procedure](https://vmware.github.io/vcd-cli/install.html).

Please note: PhotonOS 3 supports only python 3.7, while PhotonOS 4 supports only python 3.10.

One of the libraries that CSE depends on (viz. lru-dict) needs the following python packages, if these
packages are missing, CSE installtion will fail with the following error:
```
error: command 'x86_64-linux-gnu-gcc' failed with exit status 1

PhotonOS essentials for python to work with CSE
-----------------------------------------------
tdnf update
tdnf install build-essential
tdnf install python3-devel

Ubuntu OS essentials for python to work with CSE
------------------------------------------------
# x = the minor version of python 3
sudo apt install python3.x-dev
```

`Pip`, python's package manager is present by default in every python installation.
To make sure it is present and updated to its latest version, run
```
python -m ensurepip --upgrade
```

Verify python and pip installation:
```
$ python3 --version
Python 3.7.3

$ pip3 --version
pip 21.2.4 from /usr/local/lib/python3.7/site-packages/pip (python 3.7)
```

Install and verify CSE:
```
$ pip3 install container-service-extension
...

$ cse version
CSE, Container Service Extension for VMware vCloud Director, version 3.1.3
```

Alternatively, a specific version of CSE can be installed from GitHub as
follows:
```
> pip3 install git+https://github.com/vmware/container-service-extension.git@3.1.3
```

To discover available CSE source versions on GitHub see the following URL:
<https://github.com/vmware/container-service-extension/tags>


<a name="enable_cse_vcd_cli"></a>
## Enable CSE Client

After initial installation of CSE, if you try running `vcd cse` commands,
you'll probably notice an error like the the following:
```sh
> vcd cse version
Error: No such command "cse".
```
This means that the CSE client is not enabled in vcd-cli.
To enable CSE client in vcd-cli, edit `~/.vcd-cli/profiles.yaml` to include the
following (at the end of the file):
```sh
extensions:
- container_service_extension.client.cse
```
Save the file and try again. `vcd cse` commands should now work.
