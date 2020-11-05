---
layout: default
title: Known Issues
---
# Known Issues

<a name="general"></a>
## General Issues
---
### In CSE 3.0 configured with vCD 10.2, Cluster list operation may fail to retrieve results
Listing clusters either by CLI (`vcd cse cluster list`) or UI will fail if any of 
the clusters' representing defined entities are corrupted. For example, if the defined entity 
is manually modified (using direct defined entity api) and if it 
violates the schema rules of the corresponding defined entity type, then cluster 
list cmd will fail to retrieve other valid entities. 

**Workaround:** Update the defined entity with the correct schema (using direct defined entity api) 
and sync the defined entity using CSE server API - GET on `https://<vcd-ip>/api/cse/3.0/clusters/<id>`

### In CSE 3.0 configured with vCD 10.2, native clusters are stuck in _CREATE:IN_PROGRESS_ state.
When native clusters are stuck in such state, it means that the cluster 
creation has failed for unknown reason, and the representing defined entity 
has not transitioned to the ERROR state. 

**Workaround:**
1. Delete the defined entity
    * POST `https://<vcd-fqdn>/cloudapi/1.0.0/entities/<cluster-id>/resolve`
    * DEL `https://<vcd-fqdn>/cloudapi/1.0.0/entities/<cluster-id>`
2. Delete the cluster vApp. 
    * Retrieve the vApp ID. vApp Id is same as the externalID value in the 
    corresponding defined entity
        * GET `https://<vcd-fqdn>/cloudapi/1.0.0/entities/<cluster-id>`
    * Delete the corresponding cluster vApp

### In CSE 3.0 configured with vCD 10.1, prevent native clusters from getting deployed in Ent-PKS enbled ovdc(s)
As native clusters are by default allowed to be deployed on any organization 
virtual datacenters in this set-up, native clusters can inadvertently be deployed on 
Ent-PKS enbled ovdc(s). 

**Workaround:** We can prevent that by protecting native templates using template rules. 
Refer [CSE 2.6 template restriction](TEMPLATE_MANAGEMENT.html#restrict_templates).

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

