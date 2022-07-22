---
layout: default
title: Known Issues
---
# Known Issues

<a name="general"></a>
## General Issues
---

### TKG Cluster creation fails with "ACCESS_TO_RESOURCE_IS_FORBIDDEN due to lack of [VAPP_VIEW] right" even though this right is not missing
This issue is due to a security context being wiped out.

**Resolution**

This issue is fixed in CSE 3.1.4.

### Native cluster creation fails for Ubuntu 20 templates
This failure is due to a race condition in faster customer environment infrastructures.

**Resolution**

This issue is fixed in CSE 3.1.4.

### TKG cluster creation intermittently fails due to a VM reboot
This occurs due to a cloud-init script execution error when a VM is rebooted, and this issue
may be encountered as a VM postcustomization timeout.

**Resolution**

This issue is fixed in CSE 3.1.4.

### TKG cluster resize fails after 1 day of cluster creation
This issue in resizing the TKG cluster occurs because the token to join a cluster has expired. Please note that
the issue may also be encountered when trying to resize a TKG cluster that was upgraded to CSE 3.1.3 or 3.1.4.

**Resolution**

This issue is fixed in CSE 3.1.3 for newly created clusters.

**Workaround**

For clusters created prior to CSE 3.1.3, the following workaround is to create a new token and update the RDE:
1. Run the following in the control plane node: `kubeadm token create --print-join-command --ttl 0`
2. In Postman, GET the entity at: https://{{VCD_IP}}/cloudapi/1.0.0/entities/{{ENTITY_ID}}. The entity ID can be
retrieved from the cluster info page or via `vcd cse cluster info`
3. Copy the response body in (2) and replace the `kubeadm join ...` command with the output in (1) to form the request body.
4. Do a PUT on the same URL in (2) with `Content-Type: application/json` and with the request body formed in (3).
5. The resize operation can then be performed. If the resize failed, then the operation may be triggered again after (4)
due to the RDE update triggering the behavior.

### CSE Upgrade from 3.1.3 to 3.1.3 fails
The use case for upgrading from CSE 3.1.3 to 3.1.3 is needed if `cse upgrade` or `cse install` fails; in this case,
one would need to run `cse upgrade` for CSE to be able to run, but this upgrade is failing. The workaround for this
upgrade failure is to delete the CSE extension (instructions [here](CSE_SERVER_MANAGEMENT.html#uninstalling_cse_server))
and then run `cse install` again.

<a name="core_package_installation"></a>
### No kapp-controller or metrics-server version is installed or listed in the UI/CLI on TKG clusters using TKG ova 1.3.X
The compatible kapp-controller and metrics-server versions are listed in an ova's TKR bom file. For TKG ova 1.3.Z, these versions
are not found in the same sections of the TKR bom file as the sections for TKG ova's >= 1.4.0.

### Output of `vcd cse cluster info` for TKG clusters has the kubeconfig of the cluster embedded in it, while output for Native clusters don't have it.
Although both native and TKG clusters use RDE 2.0.0 for representation in VCD, they differ quite a bit in their structure.
kubeconfig content being part of the output of `vcd cse cluster info` for TKG clusters and not native clusters is by design.

### In CSE 3.1.1, `vcd-cli` prints the error `Error: 'NoneType' object is not subscriptable` to console on invoking CSE commands
This error is observed when CSE tries to restore a previously expired session and/or CSE server is down or
unreachable.

**Workaround**:
Please logout and log back in `vcd-cli` before exceuting further CSE related commands.


<a name="templates-upgrade"></a>
### In CSE 3.1, pre-existing templates will not work after upgrading to CSE 3.1 (legacy_mode=true)
After upgrade to CSE 3.1 running in legacy_mode, existing templates will not work, 
unless their corresponding scripts files are moved to the right location.
CSE 3.0.x keeps the template script files under the folder `~/.cse_scripts`, 
CSE 3.1.0 keeps them under `~./cse_scripts/<template cookbook version>`.

**Workaround(s)**:
1. Please create a folder named `~/.cse_scripts/1.0.0` and move all contents of `~/.cse_scripts` into it.
   (or)
2. Another recommended workaround is to recreate the templates.

<a name="fail_cluster_delete"></a>
### In CSE 3.1, deleting the cluster in an error state may fail from CLI/UI
Delete operation on a cluster that is in an error state (`RDE.state = RESOLUTION_ERROR` (or) `status.phase = <Operation>:FAILED`), 
may fail with Bad request (400).

**Workaround**:

VCD 10.3:

Login as the user who installed CSE (the user provided in CSE configuration file during `cse install`).

1. RDE resolution : Perform `POST https://<vcd-fqdn>/cloudapi/1.0.0/entities/{cluster-id}/resolve`
2. RDE deletion: Perform `DELETE https://<vcd-fqdn>/cloudapi/1.0.0/entities/{cluster-id}?invokeHooks=false`
3. vApp deletion: Delete the corresponding vApp from UI (or) via API call.
    - API call: Perform `GET https://<vcd-fqdn>/cloudapi/1.0.0/entities/{cluster-id}` to retrieve the
      vApp Id, which is same as the `externalID` property in the corresponding RDE. Invoke Delete vApp API.
    - UI: Identify the vApp with the same name as the cluster in the same Organization virtual datacenter and delete it.

**Update**: For VCD 10.3, please use `vcd cse cluster delete --force` to delete clusters that can't be
deleted. Learn more [here](CLUSTER_MANAGEMENT.html#force_delete).

VCD 10.2:

Login as System administrator (or) user with ADMIN_FC right on `cse:nativeCluster` entitlement

1. RDE resolution : Perform `POST https://<vcd-fqdn>/cloudapi/1.0.0/entities/{cluster-id}/resolve`
2. RDE deletion: Perform `DELETE https://<vcd-fqdn>/cloudapi/1.0.0/entities/{id}`
3. vApp deletion: Delete the corresponding vApp from UI (or) via API call.
    - API call: Perform `GET https://<vcd-fqdn>/cloudapi/1.0.0/entities/<cluster-id>` to retrieve the
      vApp Id, which is same as the `externalID` property in the corresponding RDE. Invoke Delete vApp API.
    - UI: Identify the vApp with the same name as the cluster in the same Organization virtual datacenter and delete it.

    
### In CSE 3.1, pending tasks are visible in the VCD UI right after `cse upgrade`
After upgrading to CSE 3.1 using `cse upgrade` command, you may notice pending 
tasks on RDE based Kubernetes clusters. This is merely a cosmetic issue, and it 
should not have any negative impact on the functionality. The pending tasks should 
disappear after 24 hours of timeout.

### CSE 3.1 silently ignores the `api_version` property in the config.yaml
CSE 3.1 need not be started with a particular VCD API version. It is now capable of 
accepting incoming requests at any supported VCD API version. Refer to changes in the [configuration file](CSE_CONFIG.html#api_version)

### CSE 3.1 upgrade may fail to update the clusters owned by System users correctly.
During the `cse upgrade`, the RDE representation of the existing clusters is 
transformed to become forward compatible. The newly created RDEs are supposed 
to be owned by the corresponding original cluster owners in the process. 
However, the ownership assignment may fail if the original owners are from the System org.
This is a bug in VCD.

**Workaround**:
Edit the RDE by updating the `owner.name` and `owner.id` in the payload
PUT `https://<vcd-fqdn>/cloudapi/1.0.0/entities/id?invokeHooks=false`


### Unable to change the default storage profile for Native cluster deployments
The default storage profile for native cluster deployments can't be changed in 
CSE, unless specified via CLI.

vCD follows particular order of precedence to pick the storage-profile for any VM instantiation:
1. User-specified storage-profile
2. Storage-profile with which the template is created (if VM is being instantiated from a template)
3. Organization virtual datacenter default storage-profile

**Workaround:**
1. Disable the storage-profile with which the template is created on the ovdc.
2. Set the desired storage-profile as default on the ovdc.

### Failures during template creation or installation

- One of the template creation scripts may have exited with an error
- One of the scripts may be hung waiting for a response
- If the VM has no Internet access, scripts may fail
- Check CSE logs for script outputs, to determine the cause behind the observed failure

### CSE service fails to start

- Workaround: rebooting the VM starts the service

### Cluster creation fails when VCD external network has a DNS suffix and the DNS server resolves `localhost.my.suffix` to a valid IP

This is due to a bug in **etcd** (More detail [HERE](https://github.com/kubernetes/kubernetes/issues/57709),
with the kubeadm config file contents necessary for the workaround specified in
[this comment](https://github.com/kubernetes/kubernetes/issues/57709#issuecomment-355709778)).

The main issue is that etcd prioritizes the DNS server (if it exists) over the
`/etc/hosts` file to resolve hostnames, when the conventional behavior would be
to prioritize checking any hosts files before going to the DNS server. This
becomes problematic when **kubeadm** attempts to initialize the control plane node
using `localhost`. **etcd** checks the DNS server for any entry like
`localhost.suffix`, and if this actually resolves to an IP, attempts to do some
operations involving that incorrect IP, instead of `localhost`.

The workaround (More detail [HERE](https://github.com/kubernetes/kubernetes/issues/57709#issuecomment-355709778)
is to create a **kubeadm** config file (no way to specify **listen-peer-urls**
argument in command line), and modify the `kubeadm init` command in the CSE
control plane script for the template of the cluster you are attempting to deploy.
CSE control plane script is located at
`~/.cse-scripts/<template name>_rev<template_revision>/scripts/mstr.sh`

Change command from,
`kubeadm init --kubernetes-version=v1.13.5 > /root/kubeadm-init.out`
to
`kubeadm init --config >/path/to/kubeadm.yaml > /root/kubeadm-init.out`

Kubernetes version has to be specified within the configuration file itself,
since `--kubernetes-version` and `--config` are incompatible.