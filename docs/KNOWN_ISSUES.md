---
layout: default
title: Known Issues
---
# Known Issues

<a name="general"></a>
## General Issues
---

### Fresh installation of CSE 2.5.1 or below via `pip install` is broken
CSE 2.5.1 or below versions have an open-ended dependencies, which permit `pip`
to pull and install latest versions of the dependencies. Two such dependencies
are `pyvcloud` and `vcd-cli`, and their latest available versions are
incompatible with CSE 2.5.1 or below. We are reviewing our design on
dependencies, and hope to bring improvements in near future. 

*Workaround:* - Uninstall incompatible `pyvcloud` and `vcd-cli` libraries, and
manually install compatible versions.

```sh
# Un-install pyvcloud and vcd-cli
pip3 uninstall pyvcloud vcd-cli --user --yes

#Install specific version of the libraries which are compatible with CSE 2.5.1 and CSE 2.0.0
pip3 install pyvcloud==21.0.0 vcd-cli==22.0.0 --upgrade --user
```

### `vcd cse ovdc list` operation will timeout when a large number of organization VDCs exist

CSE makes an API call per organization VDC in order to access required metadata, and that can timeout with large number of VDCs.

Example - Trying to use `vcd cse ovdc list` with 250+ VDCs:

```sh
vcd cse ovdc list
Usage: vcd cse ovdc list [OPTIONS]
Try "vcd cse ovdc list -h" for help.

Error: Unknown error. Please contact your System Administrator
```

Workaround: extend the cell timeout to be able to wait for the required amount of time. See the section 'Setting the API Extension Timeout' under [CSE Server Management](https://vmware.github.io/container-service-extension/CSE_SERVER_MANAGEMENT.html#extension-timeout).

---

### CSE server fails to start up after disabling the Service Provider Access to the Legacy API Endpoint

Workaround: Don't disable Service Provider Access to the Legacy API Endpoint

vCD 10.0 deprecates the `/api/sessions` REST end point, and introduces a new
`/cloudapi/` based REST endpoint for authenticating vCD users. CSE relies on
the '/api' end point for operations, so it is necessary that the legacy API
endpoint is not disabled in vCloud Director.

[More details](https://docs.vmware.com/en/vCloud-Director/10.0/com.vmware.vcloud.install.doc/GUID-84390C8F-E8C5-4137-A1A5-53EC27FE0024.html)

---

### Failures during template creation or installation

- One of the template creation scripts may have exited with an error
- One of the scripts may be hung waiting for a response
- If the VM has no Internet access, scripts may fail
- Check CSE logs for script outputs, to determine the cause behind the observed failure

---

### CSE service fails to start

- Workaround: rebooting the VM starts the service

---

### CSE 1.2.6 and up are incompatible with vCD 9.0

- CSE installation fails with MissingLinkException

---

### Cluster creation fails when vCD external network has a DNS suffix and the DNS server resolves `localhost.my.suffix` to a valid IP

This is due to a bug in **etcd** (More detail [HERE](https://github.com/kubernetes/kubernetes/issues/57709),
with the kubeadm config file contents necessary for the workaround specified in
[this comment](https://github.com/kubernetes/kubernetes/issues/57709#issuecomment-355709778)).

The main issue is that etcd prioritizes the DNS server (if it exists) over the
`/etc/hosts` file to resolve hostnames, when the conventional behavior would be
to prioritize checking any hosts files before going to the DNS server. This
becomes problematic when **kubeadm** attempts to initialize the master node
using `localhost`. **etcd** checks the DNS server for any entry like
`localhost.suffix`, and if this actually resolves to an IP, attempts to do some
operations involving that incorrect IP, instead of `localhost`.

The workaround (More detail [HERE](https://github.com/kubernetes/kubernetes/issues/57709#issuecomment-355709778)
is to create a **kubeadm** config file (no way to specify **listen-peer-urls**
argument in command line), and modify the `kubeadm init` command in the CSE
master script for the template of the cluster you are attempting to deploy.
CSE master script is located at
`~/.cse-scripts/<template name>_rev<template_revision>/scripts/mstr.sh`

Change command from,
`kubeadm init --kubernetes-version=v1.13.5 > /root/kubeadm-init.out`
to
`kubeadm init --config >/path/to/kubeadm.yaml > /root/kubeadm-init.out`

Kubernetes version has to be specified within the configuration file itself,
since `--kubernetes-version` and `--config` are incompatible.

---

<a name="nfs"></a>
### NFS Limitations

Currently, NFS servers in a Kubernetes cluster are not only accessible
by nodes of that cluster but also by any VM (outside of the cluster)
residing in the same orgVdc. Ideal solution is to have vApp network
created for each Kubernetes cluster, which is in our road-map to
implement. Until then, please choose one of below workarounds to
avert this problem if the need arises.

* Give access to only master & worker nodes of the cluster by adding individual
  IPs of the nodes into /etc/exports file on NFS server.
    * Create and run a script periodically which retrieves IPs of nodes in the
      cluster and then add them to NFS server access list (/etc/exports).
    ```sh
       /home 203.0.113.256(rw,sync,no_root_squash,no_subtree_check) 203.0.113.257(rw,sync,no_root_squash,no_subtree_check)
    ```
* Administrator can manually add a vApp network for each Kubernetes cluster in vCD.
* Create a ssh tunnel from each worker node (using ssh local port forwarding) and then
  use `127.0.0.1:<port>` in the Kubernetes declarative specs as IP of the NFS server.
    * In NFS server, for any given shared directory, add below line to `/etc/exports` file.
      * `/home localhost(insecure,rw,sync,no_subtree_check)`
      * `systemctl restart nfs-kernel-server.service`
      * Copy ssh public key of each worker node into `~/.ssh/authorized_keys` in NFS server
    * Client: Generate key using `ssh-keygen` and copy the contents of `~/.ssh/id_rsa.pub`
    * NFS server: Paste the contents (public key) from client into `~/.ssh/authorized_keys`
    * In each master/worker node,
      * `apt-get install portmap`
      * `ssh -fNv -L 3049:127.0.0.1:2049 user@NFSServer`
    * Read more about this approach at
      * http://www.debianadmin.com/howto-use-ssh-local-and-remote-port-forwarding.html
      * https://gist.github.com/proudlygeek/5721498

---

<a name="ent-pks"></a>
## Enterprise PKS Limitations

* When attaching an NSX-T-backed vCenter (such as Enterprise PKS vCenter) to a
MicrosoftSQL-backed vCD, the vCenter can fail to connect. Refer to this
[work around](https://docs.vmware.com/en/vCloud-Director/9.7/rn/vmware-vcloud-director-for-service-providers-97-release-notes.html)
* Command `vcd cse node info` on native K8 clusters is broken when
Enterprise PKS is part of CSE set-up
* Once `vcd cse cluster resize` is run on Enterprise PKS based clusters,
organization administrator's attempts to view and perform CRUD operations on those
clusters will begin to fail with errors.
* Once `vcd cse cluster resize` is run on Enterprise PKS based clusters, commands
`vcd cse cluster info` and `vcd cse cluster list` on those resized clusters will begin to display
incomplete results.
* Once a given organization vdc is enabled for Enterprise PKS,
renaming that organization vdc in vCD will cause further K8 cluster deployment
failures in that organization vdc.
