---
layout: default
title: CSE Server Configuration File
---

## CSE Server Configuration File

The CSE server installation as well runtime is controlled by a yaml
configuration file that must be filled out prior to installation. You can
generate a skeleton file as follows.

```sh
cse sample -o config.yaml
```

Edit this file to add values from your vCloud Director installation. The
following example shows a file with sample values filled out.

```yaml
amqp:
  exchange: cse-ext
  host: amqp.vmware.com
  password: guest
  port: 5672
  prefix: vcd
  routing_key: cse
  ssl: false
  ssl_accept_all: false
  username: guest
  vhost: /

vcd:
  api_version: '33.0'
  host: vcd.vmware.com
  log: true
  password: my_secret_password
  port: 443
  username: administrator
  verify: true

vcs:
- name: vc1
  password: my_secret_password
  username: cse_user@vsphere.local
  verify: true
- name: vc2
  password: my_secret_password
  username: cse_user@vsphere.local
  verify: true

service:
  enforce_authorization: false
  listeners: 5
  log_wire: false

broker:
  catalog: cse
  default_template_name: my_template
  default_template_revision: 0
  ip_allocation_mode: pool
  network: mynetwork
  org: myorg
  remote_template_cookbook_url: https://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template.yaml
  storage_profile: '*'
  vdc: myorgvdc

# [Optional] Template rule section
# Rules can be defined to override template definitions as defined by remote
# template cookbook.
# Any rule defined in this section can match exactly one template.
# Template name and revision must be provided for the rule to be processed.
# Templates will still have the default attributes that were defined during template creation.
# These newly defined attributes only affect new cluster deployments from templates.
# Template rules can override the following attributes:
# * compute_policy
# * cpu
# * memory

# Example 'template_rules' section:

#template_rules:
#- name: Rule1
#  target:
#    name: photon-v2_k8-1.12_weave-2.3.0
#    revision: 1
#  action:
#    compute_policy: "sample policy"
#    cpu: 4
#    mem: 512
#- name: Rule2
#  target:
#    name: my_template
#    revision: 2
#  action:
#    cpu: 2
#    mem: 1024

# This key should only be used if using Enterprise PKS with CSE.
# Value should be a filepath to PKS config file.

pks_config: null
```

The config file has 5 mandatory sections (`amqp`, `vcd`, `vcs`, `service`,
and, `broker`) and 1 optional section (`template_rules`). The following
sub-sections explain the configuration properties for each section as well as
how they are used.

### `amqp` Section

During CSE Server installation, CSE will set up AMQP to ensure
communication between vCD and the running CSE server. The `amqp`
section controls the AMQP communication parameters. The following
properties will need to be set for all deployments.

| Property | Value |
|-|-|
| host | IP or hostname of the vCloud Director AMQP server (may be different from the vCD cell hosts) |
| username | Username of the vCD service account with minimum roles and rights |
| password | Password of the vCD service account |

Other properties may be left as is or edited to match site conventions.

For more information on AMQP settings, see the [vCD API documentation on AMQP](https://code.vmware.com/apis/442/vcloud#/doc/doc/types/AmqpSettingsType.html).

### `vcs` Section

Properties in this section supply credentials necessary for the following operations:

* Guest Operation Program Execution
* Guest Operation Modifications
* Guest Operation Queries

Each `vc` under the `vcs` section has the following properties:

| Property | Value |
|-|-|
| name | Name of the vCenter registered in vCD |
| username | Username of the vCenter service account with minimum of guest-operation privileges |
| password | Password of the vCenter service account |

Note : All VCs registered in vCD must be listed here, otherwise CSE server
installation will fail during pre-check phase.

<a name="service_section"></a>
### `service` Section

The service section contains properties that define CSE server behavior.

| Property | Value |
|-|-|
| listeners | Number of threads that CSE server should use |
| enforce_authorization | If True, CSE server will use role-based access control, where users without the correct CSE right will not be able to deploy clusters (Added in CSE 1.2.6) |
| log_wire | If True, will log all REST calls initiated by CSE to vCD. (Added in CSE 2.5.0) |

<a name="broker"></a>
### `broker` Section

The `broker` section contains properties to define resources used by
the CSE server including org and VDC as well as template repository location.
The following table summarizes key parameters.

| Property | Value |
|-|-|
| catalog | Publicly shared catalog within `org` where K8s templates will be published |
| default_template_name | Name of the default template to use if none is specified during cluster and node operations. CSE server won't start up if this value is invalid. (Added in CSE 2.5.0) |
| default_template_revision | Revision of the default template to use if none is specified during cluster and node operations.  CSE server won't start up if this value is invalid. (Added in CSE 2.5.0) |
| ip_allocation_mode | IP allocation mode to be used during the install process to build the template. Possible values are `dhcp` or `pool`. During creation of clusters for tenants, `pool` IP allocation mode is always used |
| network | Org Network within `vdc` that will be used during the install process to build the template. It should have outbound access to the public Internet. The `CSE` appliance doesn't need to be connected to this network |
| org | vCD organization that contains the shared catalog where the K8s templates will be stored |
| remote_template_cookbook_url | URL of the template repository where all template definitions and associated script files are hosted. (Added in CSE 2.5.0) |
| storage_profile | Name of the storage profile to use when creating the temporary vApp used to build the template |
| vdc | Virtual data-center within `org` that will be used during the install process to build the template |

<a name="templte_rules"></a>
### `template_rules` Section
(Added in CSE 2.5.0)\
Rules can be created to override some of the default attributes of templates
defined by the remote template repository.

This section can contain zero or more such rules, each rule matches exactly one
template. Matching is driven by name and revision of the template. If only name
is specified without the revision or vice versa, the rule will not be
processed.

Each rule comprises of the following attributes

| Property | Value |
|-|-|
| name | Name of the rule |
| target | Name and revision of the template on which the rule will be applied |
| action | Template properties that will be overridden. Only supported properties are `compute_policy`, `cpu`, and `memory` |

Please refer to [Restricting Kubernetes templates](/container-service-extension/TEMPLATE_MANAGEMENT.html#restrict_templates)
for further details on compute policies.

<a name="pksconfig"></a>
### `pks_config` property

Filling out this key for regular CSE set up is optional and should be left
as is. Only for CSE set up enabled for [Enterprise PKS](/container-service-extension/ENT_PKS.html)
container provider, this value needs to point to absolute path of valid Enterprise PKS config file.
Please refer to [Enterprise PKS enablement](/container-service-extension/ENT_PKS.html) for more details.

Enabling Enterprise PKS as a K8s provider changes the default behavior of CSE as described below.
Presence of valid value for `pks_config` property gives an indication to CSE that
Enterprise PKS is enabled (in addition to Native vCD) as a K8s provider in the system.

- CSE begins to mandate any given `ovdc` to be enabled for either Native or Enterprise PKS as a backing K8s provider.
Cloud Administrators can do so via `vcd cse ovdc enable` command. This step is mandatory for ovdc(s) with
preexisting native K8s clusters as well i.e., if CSE is upgraded from 1.2.x to 2.0 and `pks_config`
is set, then it becomes mandatory to enable those ovdc(s) with pre-existing native K8s clusters.
- In other words, If `pks_config`  value is present and if an ovdc is not enabled for either of the supported
K8s providers, users will not be able to do any further K8s deployments in that ovdc.

In the absence of value for `pks_config` key, there will not be any change in CSE's default behavior i.e.,
any ovdc is open for native K8s cluster deployments.

#### Enterprise PKS Config file
```yaml
# Enterprise PKS config file to enable Enterprise PKS functionality on CSE
# Please fill out the following four sections:
#   1. pks_api_servers:
#       a. Each entry in the list represents a Enterprise PKS api server
#          that is part of the deployment.
#       b. The field 'name' in each entry should be unique. The value of
#          the field has no bearing on the real world Enterprise PKS api
#          server, it's used to tie in various segments of the config file
#          together.
#       c. The field 'vc' represents the name with which the Enterprise PKS
#          vCenter is registered in vCD.
#       d. The field 'cpi' needs to be retrieved by executing
#          'bosh cpi-config' on Enterprise PKS set up.
#   2. pks_accounts:
#       a. Each entry in the list represents a Enterprise PKS account that
#          can be used talk to a certain Enterprise PKS api server.
#       b. The field 'name' in each entry should be unique. The value of
#          the field has no bearing on the real world Enterprise PKS
#          accounts, it's used to tie in various segments of the config
#          file together.
#       c. The field 'pks_api_server' is a reference to the Enterprise PKS
#          api server which owns this account. It's value should be equal to
#          value of the field 'name' of the corresponding Enterprise PKS api
#          server.
#   3. pvdcs:
#       a. Each entry in the list represents a Provider VDC in vCD that is
#          backed by a cluster of the Enterprise PKS managed vCenter server.
#       b. The field 'name' in each entry should be the name of the
#          Provider VDC as it appears in vCD.
#       c. The field 'pks_api_server' is a reference to the Enterprise PKS
#          api server which owns this account. Its value should be equal to
#          value of the field 'name' of the corresponding Enterprise PKS api
#          server.
#   4. nsxt_servers:
#       a. Each entry in the list represents a NSX-T server that has been
#          alongside an Enterprise PKS server to manage its networking. CSE
#          needs these details to enforce network isolation of clusters.
#       b. The field 'name' in each entry should be unique. The value of
#          the field has no bearing on the real world NSX-T server, it's
#          used to tie in various segments of the config file together.
#       c. The field 'pks_api_server' is a reference to the Enterprise PKS
#          api server which owns this account. Its value should be equal to
#          value of the field 'name' of the corresponding Enterprise PKS api
#          server.
#       d. The field 'distributed_firewall_section_anchor_id' should be
#          populated with id of a Distributed Firewall Section e.g. it can
#          be the id of the section called 'Default Layer3 Section' which
#          Enterprise PKS creates on installation.
# For more information, please refer to CSE documentation page:
# https://vmware.github.io/container-service-extension/INSTALLATION.html

pks_api_servers:
- clusters:
  - pks-s1-az-1
  - pks-s1-az-2
  - pks-s1-az-3
  cpi: cpi1
  datacenter: pks-s1-dc
  host: pks-api-server-1.pks.local
  name: pks-api-server-1
  port: '9021'
  uaac_port: '8443'
  vc: vc1
  verify: true
- clusters:
  - pks-s2-az-1
  - pks-s2-az-2
  - pks-s2-az-3
  cpi: cpi2
  datacenter: pks-s2-dc
  host: pks-api-server-2.pks.local
  name: pks-api-server-2
  port: '9021'
  uaac_port: '8443'
  vc: vc2
  verify: true

pks_accounts:
- name: Org1ServiceAccount1
  pks_api_server: pks-api-server-1
  secret: secret
  username: org1Admin
- name: Org1ServiceAccount2
  pks_api_server: pks-api-server-2
  secret: secret
  username: org1Admin
- name: Org2ServiceAccount
  pks_api_server: pks-api-server-2
  secret: secret
  username: org2Admin

pvdcs:
- cluster: pks-s1-az-1
  name: pvdc1
  pks_api_server: pks-api-server-1
- cluster: pks-s2-az-1
  name: pvdc2
  pks_api_server: pks-api-server-2
- cluster: pks-s1-az-2
  name: pvdc3
  pks_api_server: pks-api-server-1

nsxt_servers:
- distributed_firewall_section_anchor_id: id
  host: nsxt1.domain.local
  name: nsxt-server-1
  nodes_ip_block_ids:
  - id1
  - id2
  password: my_secret_password
  pks_api_server: pks-api-server-1
  pods_ip_block_ids:
  - id1
  - id2
  username: admin
  verify: true
- distributed_firewall_section_anchor_id: id
  host: nsxt2.domain.local
  name: nsxt-server-2
  nodes_ip_block_ids:
  - id1
  - id2
  password: my_secret_password
  pks_api_server: pks-api-server-2
  pods_ip_block_ids:
  - id1
  - id2
  username: admin
  verify: true
```
