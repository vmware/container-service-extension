---
layout: default
title: Known Issues
---
# Known Issues

<a name="general"></a>
## General Issues
---
### (CSE 3.0 - vCD 10.2) Cluster delete operation may leave stale entries for native clusters.
On cluster delete operation, if native cluster deletion fails for any unknown 
reason, CLI and UI sometimes may give out a false impression that the cluster 
has been deleted successfully. The reason being the corresponding defined entity 
may get deleted; however, the actual cluster vapp deletion may have failed. It 
is best to track the cluster deletion with the task_href, until the issue is fixed.
As a workaround, manually delete the stale vApp VMs.

### (CSE 3.0 - vCD 10.2) Cluster list operation may fail to retrieve results
Listing clusters either by CLI (vcd cse cluster list) or UI will fail if any of 
the clusters' defined entities are corrupted. For example, if the defined entity 
is manually modified (using defined entity api directly) to the extent that it 
violates the schema rules of the corresponding defined entity type, then cluster 
list cmd will fail to retrieve other valid entities. As a workaround, carefully 
update the defined entity with the correct schema and [sync the defined entity](TROUBLESHOOTING.html#sync-def-entity) 
using CSE server API.
    
### Existing clusters show Kubernetes version as 0.0.0 after CSE is upgraded to 2.6.0
The way Kubernetes version of a cluster is determined, changed between
CSE 2.5.x and 2.6.0. If the cluster metadata is not properly updated, then
CSE 2.6.0 defaults the version to 0.0.0.

*Workaround:* CSE 2.6.1 takes care of this issue and defaults to the Kubernetes
version of the template from which the cluster is deployed. However, please note
that if the template itself was created by CSE 2.5.x, then this approach is not
foolproof. In such cases it's better to recreate the template in CSE 2.6.1, and
then run `cse convert-cluster` command against the affected cluster to fix its
metadata. Possible error messages if the template is not recreated and
`cse convert-cluster` is not run are as follows (but not limited to):

N/A or patch version missing in/from Kubernetes version field
```sh
$ vcd cse cluster list
Name                        VDC          Org      Kubernetes      Status      Provider
--------------------------  -----------  -------  --------------  ----------  ----------
used_old_tempalte           new-org-vdc  new-org  upstream 1.16   POWERED_ON  native
didn_t_run_cluster_convert  new-org-vdc  new-org  N/A             POWERED_ON  native
```

Kubernetes upgrade operation fails
```sh
$ vcd cse cluster upgrade "used_old_tempalte" ubuntu-16.04_k8-1.17_weave-2.6.0 1
cluster operation: Upgrading cluster 'used_old_tempalte' software to match template
ubuntu-16.04_k8-1.17_weave-2.6.0 (revision 1): Kubernetes: 1.16 -> 1.17.2,
Docker-CE: 18.09.7 -> 19.03.5, CNI: weave 2.6.0 -> 2.6.0,
.
.
task: [REDACTED uuid], result: error, message: Unexpected error while upgrading
cluster 'used_old_tempalte': Invalid version string: '1.16'
```

---
### Never ending CSE tasks in VCD UI / Failed CSE tasks without proper error message
If CSE server encounters any error during cluster/node creation, users may see
CSE tasks in VCD never reach to completion, or the tasks may show up as failed
without a proper error message. Currently, UI lacks the ability to properly
express error messages upon operation failures. Some examples might be - A user
input parameter was invalid, or an unexpected error (network connection/outage)
occurred. Please inspect CSE server logs in these cases, or file a github
[issue](https://github.com/vmware/container-service-extension/issues).

---
### Fresh installation of CSE 2.5.1 or below via `pip install` is broken
CSE 2.5.1 or below versions have an open-ended dependencies, which permit `pip`
to pull and install latest versions of the dependencies. Two such dependencies
are `pyvcloud` and `vcd-cli`, and their latest available versions are
incompatible with CSE 2.5.1 or below. We are reviewing our design on
dependencies, and hope to bring improvements in near future.

*Workaround:* - Un-install incompatible `pyvcloud` and `vcd-cli` libraries, and
manually install compatible versions.

```sh
# Un-install pyvcloud and vcd-cli
pip3 uninstall pyvcloud vcd-cli --user --yes

#Install specific version of the libraries which are compatible with CSE 2.5.1 and CSE 2.0.0
pip3 install pyvcloud==21.0.0 vcd-cli==22.0.0 --upgrade --user
```
---
### `vcd cse ovdc list` operation will timeout when numerous OrgVDCs exist

CSE makes an API call per OrgVDC in order to access required metadata, and that
can timeout with large number of OrgVDCs.

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

VCD 10.0 deprecates the `/api/sessions` REST end point, and introduces a new
`/cloudapi/` based REST endpoint for authenticating VCD users. CSE relies on
the '/api' end point for operations, so it is necessary that the legacy API
endpoint is not disabled in vCloud Director.

[More details](https://docs.vmware.com/en/vCloud-Director/10.0/com.vmware.vcloud.install.doc/GUID-84390C8F-E8C5-4137-A1A5-53EC27FE0024.html)

**Update** : CSE 2.6.0 has resolved this issue.

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
### CSE 1.2.6 and up are incompatible with VCD 9.0

- CSE installation fails with MissingLinkException

---
### Cluster creation fails when VCD external network has a DNS suffix and the DNS server resolves `localhost.my.suffix` to a valid IP

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
residing in the same OrgVDC. Ideal solution is to have vApp network
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
* Administrator can manually add a vApp network for each Kubernetes cluster in VCD.
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
MicrosoftSQL-backed VCD, the vCenter can fail to connect. Refer to this
[work around](https://docs.vmware.com/en/vCloud-Director/9.7/rn/vmware-vcloud-director-for-service-providers-97-release-notes.html)
* Command `vcd cse node info` on native K8 clusters is broken when
Enterprise PKS is part of CSE set-up
* Once `vcd cse cluster resize` is run on Enterprise PKS based clusters,
organization administrator's attempts to view and perform CRUD operations on those
clusters will begin to fail with errors.
* Once `vcd cse cluster resize` is run on Enterprise PKS based clusters, commands
`vcd cse cluster info` and `vcd cse cluster list` on those resized clusters will begin to display
incomplete results.
* Once a given OrgVDC is enabled for Enterprise PKS,
renaming that OrgVDC in VCD will cause further K8 cluster deployment
failures in that OrgVDC.
