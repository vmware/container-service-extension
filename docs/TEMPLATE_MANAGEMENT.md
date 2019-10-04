---
layout: default
title: Kubernetes Template Management
---
# Kubernetes Template Management

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

<a name="creating_kubernetes_templates"></a>
### Creating Kubernetes Templates
During CSE server installation, CSE provides the option to create Kubernetes
templates from all template definitions available at the remote repository
URL specified in the [config file](/container-service-extension/CSE_CONFIG.html#broker).
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
cse template install TEMPLATE_NAME TEMPLATE_REVISION
```
The refreshed templates do not impact existing Kubernetes clusters in the
environment.

<a name="restrict_templates"></a>
## Restricting Kubernetes Templates for Tenants

Out of the box, Kubernetes templates are not restricted for use. All tenants
have access to all the Kubernetes templates to deploy Kubernetes clusters, as
long as they have sufficient permissions to interact with CSE. However,
starting from CSE 2.5, service providers have the option to selectively
restrict Kubernetes templates from being used by tenants in order to prohibit
them from deploying Kubernetes Clusters.

This is accomplished with the use of VDC Compute Policies feature of vCD 10.0.
CSE 2.5 offers the capability to service providers to tag selected templates
and organization VDCs with compute policy which restricts Kubernetes cluster
deployments from tagged templates to only tagged organization VDCs.

### Enable Restriction on Kubernetes Templates
Restriction on Kubernetes templates is enabled by leveraging the [template_rules
section](/container-service-extension/CSE_CONFIG.html#templte_rules) in CSE
config file. Service Providers can mark Kubernetes templates as _protected_ by
tagging them with a `VdcComputePolicy`. To do so, Service Providers need to
define a template rule in the `template_rules` section, whose target is the
template to protect, and as `action` a value must be specified for the key
`compute_policy`.
```yaml
template_rules:
- name: Photon Template Rule
  target:
    name: photon-v2_k8-1.12_weave-2.3.0
    revision: 1
  action:
    compute_policy: "Photon Template Policy"
```
Service providers select the name of the compute policy per their choice, and
CSE creates that compute policy in vCD, if it's not already present. During CSE
server startup, the template rule "Photon Template Rule" is processed and the
defined Kubernetes template is tagged with the compute policy. At this point,
the Kubernetes template is restricted from further use, until tenant
organization VDCs are enabled with matching compute policy to permit Kubernetes
cluster deployments.

### Grant Tenants access to Kubernetes Templates
Service providers select tenants to whom they want to grant access of certain
Kubernetes Templates based cluster deployments. Then, they enable selected
tenants' organization VDCs with the same compute policy as present on the
Kubernetes Template. To do so, the following command should be used
```sh
vcd cse ovdc compute-policy add ORG_NAME OVDC_NAME POLICY_NAME
```

### Revoke Permission to use Kubernetes Templates from Tenants
Permission to use a protected template can be revoked at any time from the
tenant, via the following command.
```sh
vcd cse ovdc compute-policy remove ORG_NAME OVDC_NAME POLICY_NAME
```
If there are Kubernetes clusters in that organization VDC, use `-f/--force`
flag to force the operation. The clusters will remain deployed, and will
switch to `System Default` compute policy.

### Remove restriction from Kubernetes Templates
In order to remove the restriction from Kubernetes templates, Service providers
can delete the template rule from the config file and restart the CSE server.
Alternatively, the same outcome can be achieved by specifying an empty policy
name in the concerned rule.
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
