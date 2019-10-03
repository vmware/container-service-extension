---
layout: default
title: Template Management
---
# Template Management

<a name="overview"></a>
## Overview
CSE uses customized VM templates (Kubernetes templates) as building blocks for
deployment of Kubernetes clusters. These templates are crucial for CSE to
function properly. This document describes the various aspects of these
Kubernetes templates including their life cycle management.

<a name="kubernetes_templates"></a>
## Kubernetes Templates

`CSE 2.5` supports deploying Kubernetes clusters from multiple Kubernetes
templates. Templates vary by guest OS (e.g. PhotonOS, Ubuntu), as well as,
software versions, like Kubernetes, Docker, or Weave. Each template name is
uniquely constructed based on the flavor of guest OS, Kubernetes version, and
the Weave software version. The definitions of different templates reside in an
official location hosted at a remote repository URL. The CSE sample config
file, out of the box, points to the official location of those templates
definitions. The remote repository is officially managed by maintainers of the
CSE project.

### Creating Kubernetes Templates
During CSE server installation, CSE provides the option to create Kubernetes
templates from all template definitions available at the remote repository
URL specified in the [config file](/container-service-extension/CSE_CONFIG.html).
Alternatively, Service Providers have the option to install CSE server with
`--skip-template-creation` flag, if specified CSE does not create any
Kubernetes templates during installation. Once CSE server installation is
complete, Service Providers can create selective Kubernetes templates using the
 following command.
```sh
cse template list
cse template install TEMPLATE_NAME TEMPLATE_REVISION
```

### Using Kubernetes Templates
While starting the CSE server, a default Kubernetes template and revision must
be specified in the config file, for CSE server to successfully start up.
Tenants can always override the default templates via specifying their choice
of revision of a template during cluster operations like
`vcd cse cluster create`, `vcd cse cluster resize`, and `vcd cse node create`.

### Updating Kubernetes Templates

Service Providers can expect newer templates as updates to OS versions,
Kubernetes major or minor versions, or Weave major or minor versions are made
available. They can also expect revised templates (through a change to the
revision of existing templates) with updated Kubernetes patch versions.
Service Providers can refresh their existing templates with revised versions or
install new templates by using below command. Please note that a graceful shut
down of CSE Server is advised before attempting to update the templates.
```sh
cse template list --display diff
cse template install [OPTIONS] TEMPLATE_NAME TEMPLATE_REVISION
```
The refreshed templates do not impact existing Kubernetes clusters in the
environment.

<a name="restrict_templates"></a>
## Restricting Kubernetes Templates for Tenants
Out of the box, Kubernetes templates are not restricted for use. All tenants
have access to Kubernetes templates to deploy Kubernetes clusters, as long as
they have sufficient permissions to interact with CSE. However, starting from
CSE 2.5, service providers have the option to selectively restrict Kubernetes
templates from being used by tenants in order to prohibit them from deploying
Kubernetes Clusters.

### Protecting Kubernetes Templates
CSE uses vCD's `VdcComputePolicy` to enforce this tenant level restriction.
Service Providers can mark Kubernetes templates as _protected_ by tagging them
with a `VdcComputePolicy`. To do so, Service Providers need to define a
template rule in the config section, whose target is the template to protect,
and as `action` a value must be specified for the key `compute-policy`.
```yaml
template_rules:
- name: Rule1
  target:
    name: photon-v2_k8-1.12_weave-2.3.0
    revision: 1
  action:
    compute_policy: "Policy for Tenant 1"
```
The name of the compute policy can be chosen by service provider at will, CSE
will create the policy if it's already not present in vCD. Also, the name of
the policy will be internally qualified by CSE to make sure it doesn't
interfere with regular compute policies in vCD. Once the rule is processed
during CSE server startup, the desired compute policy will be assigned to the
Kubernetes template. And any request to deploy a Kubernetes cluster using the
template will fail unless the org VDC on which the cluster is being deployed
supports the afore-mentioned compute policy.

### Granting Tenants Permission to use Kubernetes Templates
Service provider can selectively choose tenants whom they want to give access
to the template by adding the compute policy to the relevant org VDC(s). To do
so, they can utilize the following command.
```sh
vcd cse ovdc compute-policy add ORG_NAME OVDC_NAME POLICY_NAME
```

### Revoking Permission to use Kubernetes Templates from Tenants
Permission to use a protected template can be revoked at any time from the
tenant, via the following command.
```sh
vcd cse ovdc compute-policy remove ORG_NAME OVDC_NAME POLICY_NAME
```
If there are deployed cluster that are referencing the compute policy, then
-f/--force flag should be used to force the operation. All such clusters will
remain deployed but revert to `System Default` compute policy.

### Removing Protection status from a Kubernetes Templates
To remove the _protected_ status of a template, service provider can simply
delete the rule that assigns the compute policy to the template and restart
the CSE server. In future, if there are templates that are _protected_ out of
box, in that case the rule need to tweaked to specify an empty policy to get
rid of the _protection_.
```yaml
template_rules:
- name: Rule1
  target:
    name: out_of_box_protected_tempalte
    revision: 1
  action:
    compute_policy: ""
```

<a name="template_os_source"></a>
## Source .ova Files for Kubernetes Templates

The following table lists URLs of the OVA files that are used as the base for
the Kubernetes templates.

| OS | OVA Name | URL | SHA256 |
|-|-|-|-|
| Photon OS 2.0 GA     | photon-custom-hw11-2.0-304b817.ova | `http://dl.bintray.com/vmware/photon/2.0/GA/ova/photon-custom-hw11-2.0-304b817.ova`                       | cb51e4b6d899c3588f961e73282709a0d054bb421787e140a1d80c24d4fd89e1 |
| Ubuntu 16.04.4 LTS   | ubuntu-16.04-server-cloudimg-amd64.ova | `https://cloud-images.ubuntu.com/releases/xenial/release-20180418/ubuntu-16.04-server-cloudimg-amd64.ova` | 3c1bec8e2770af5b9b0462e20b7b24633666feedff43c099a6fb1330fcc869a9 |
