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

| User Type | Task(s)
|-----------|--------
| Kubernetes user | Install kubectl on laptop or workstation
| Org admin managing K8s clusters | Install CSE and configure CSE client on laptop or VM
| Cloud admin installing CSE in vCD | Install CSE on server host

Naturally a cloud admin may install the CSE client to test cluster
creation after CSE server setup. Similarly a tenant org administrator
may install kubectl to check Kubernetes clusters or perform
administrative tasks.

<a name="kubectl"></a>
## Install Kubectl

Install kubectl using directions from the [Kubernetes web site](https://kubernetes.io/docs/tasks/tools/install-kubectl/).

<a name="gettingcse"></a>
## Install CSE Software

Install Python 3.6 or greater. See Python installation instructions and
downloads at <https://www.python.org> or consult the [vcd-cli install
procedure](https://vmware.github.io/vcd-cli/install.html).  Pip, Python's
package manager comes with Python.

Verify python and pip installation:
```sh
$ python3 --version
Python 3.7.0

$ pip3 --version
pip 18.0 from /usr/local/lib/python3.7/site-packages/pip (python 3.7)
```

Now install and verify CSE:
```sh
$ pip3 install container-service-extension
...

$ cse version
CSE, Container Service Extension for VMware vCloud Director, version 1.2.5
```

Alternatively, a specific version of CSE can be installed from GitHub as
follows:
```sh
> pip3 install git+https://github.com/vmware/container-service-extension.git@1.2.4
```
*NOTE:* pip3 install from git fails on virtual environments created by
`python3 -m venv`.  See <https://github.com/vmware/container-service-extension/issues/181> for details and workaround.

To discover available CSE source versions on GitHub see the following URL:
<https://github.com/vmware/container-service-extension/tags>

---
<a name="csevcdcli"></a>
## Enable CSE Client

After initial installation you'll see a response like the following
when running `vcd cse` commands, which means that the CSE client
is not enabled.
```sh
> vcd cse version
Error: No such command "cse".
```
To enable edit `~/.vcd-cli/profiles.yaml` to include this section:
```
extensions:
- container_service_extension.client.cse
```
Save the file and try again. `vcd cse` commands should now work.
