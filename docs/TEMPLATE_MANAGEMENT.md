---
layout: default
title: Template Management
---
# Template Management

## Overview
CSE uses customized VM templates (Kubernetes templates) as building blocks for
deployment of Kubernetes clusters. These templates are crucial for CSE to
function properly. This documents describes the various aspects of these
kubernetes templates including their life cycle management.

<a name="vmtemplates"></a>
## K8s Templates

`CSE 2.5` supports deploying Kubernetes clusters from multiple K8s templates.
Templates vary by guest OS, like Photon, Ubuntu, as well as, software versions,
like Kubernetes, Docker, or Weave. Each template name is uniquely constructed
based on the flavor of guest OS, K8s version, and the Weave software version.
The definitions of different templates reside in an official location hosted at
a remote repository URL. The CSE sample config file, out of the box, points to
the official location of those templates definitions. The remote repository is
officially managed by maintainers of the CSE.

Service Providers can expect newer templates as updates to OS versions, K8s
major or minor versions, or Weave major or minor versions are made available.
They can also expect revised templates (through a change to the revision of
existing templates) with updated K8s micro versions. 

During CSE installation, CSE creates all the K8s templates for all template
definitions available at the remote repository URL specified in the config
file. Alternatively, Service Providers have the option to install CSE with
`--skip-template-creation` option, if specified CSE does not create any K8s
templates. Service Providers can subsequently create selective K8s templates
using the following command.
```sh
cse template list
cse template install [OPTIONS] TEMPLATE_NAME TEMPLATE_REVISION
```
Please note that a default K8s template and revision must be specified in the
config file for CSE server to successfully start up. Tenants can always
override the default templates via specifying their choice of revision of a
template during cluster operations like `vcd cse cluster create`,
`vcd cse cluster resize`, and `vcd cse node create`.

### Source .ova Files for K8s Templates

The following table lists URLs of the OVA files that are used as the base for
the K8s templates.

| OS | OVA Name | URL | SHA256 |
|-|-|-|-|
| Photon OS 2.0 GA     | photon-custom-hw11-2.0-304b817.ova | `http://dl.bintray.com/vmware/photon/2.0/GA/ova/photon-custom-hw11-2.0-304b817.ova`                       | cb51e4b6d899c3588f961e73282709a0d054bb421787e140a1d80c24d4fd89e1 |
| Ubuntu 16.04.4 LTS   | ubuntu-16.04-server-cloudimg-amd64.ova | `https://cloud-images.ubuntu.com/releases/xenial/release-20180418/ubuntu-16.04-server-cloudimg-amd64.ova` | 3c1bec8e2770af5b9b0462e20b7b24633666feedff43c099a6fb1330fcc869a9 |

### Updating K8s Templates

K8s Template definitions will be updated with newer software packages or
configuration changes from time to time at the remote repository by CSE
maintainers. Service Providers can refresh their existing templates with
revised versions or install new templates by using below command. Please note
that a graceful shut down of CSE Server is advised before attempting to update
the templates.
```sh
cse template list --display diff
cse template install [OPTIONS] TEMPLATE_NAME TEMPLATE_REVISION
```
The refreshed templates do not impact existing K8s clusters in the environment.

### Restricting Templates usage by Tenants
Out of box Kubernetes templates don't have any restriction on them, and can
be used to deploy clusters by any tenant user with sufficient permissions to
interact with CSE. However, starting from CSE 2.5, service providers can
selectively restrict tenants from using certain templates to create Kubernetes
clusters. This is achieved by utilizing `VdcComputePolicy` in vCD.
Service providers can mark Kubernetes templates as _protected_ by tagging them
with a `VdcComputePolicy`. To do so, service providers need to define a
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
The name of the compute policy can be chosen by servvice provider at will, CSE
will create the policy if it's already not present in vCD. Also, the name of
the policy will be internally qualified by CSE to make sure it doesn't
interfere with regular compute polcies in vCD. Once the rule is processed
during CSE server startup, the desired compute policy will be assigned to the
Kubernetes template. And any request to deploy a Kubernetes cluster using the
template will fail unless the org VDC on which the cluster is being deployed
supports the afore-mentioned compute policy. Service provider can selectively
choose tenants whom they want to give access to the template by adding the
compute policy to the relevant org VDC(s). To do so, they can utilize the
folllowing command.
```sh
vcd cse ovdc compute-policy add ORG_NAME OVDC_NAME POLICY_NAME
```
Permission to use a protected template can be revoked at any time from the
tenant, via the following command.
```sh
vcd cse ovdc compute-policy remove ORG_NAME OVDC_NAME POLICY_NAME
```
If there are deployed cluster that are referencing the compute policy, then
-f/--force flag should be used to force the operation. All such clusters will
remain deployed but revert to `System Default` compute policy.

To remove the _protected_ status of a template, service provider can simply
delete the rule that assigns the compute policy to the template and restart
the CSE server. In future, if there is a template that is _protected_ out of
box, in that case the rule need to tweeked to specify an empty policy to get
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
