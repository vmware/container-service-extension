---
layout: default
title: CSE Server Configuration File
---

<a name="cse_config"></a>
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
  listeners: 10
  log_wire: false
  telemetry:
    enable: true

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

| Property | Value                                                                                        |
|----------|----------------------------------------------------------------------------------------------|
| exchange | Exchange name unique to CSE (CSE will create and use this exchange to communicate with vCD)  |
| host     | IP or hostname of the vCloud Director AMQP server (may be different from the vCD cell hosts) |
| username | AMQP username                                                                                |
| password | AMQP password                                                                                |

Other properties may be left as is or edited to match site conventions.

For more information on AMQP settings, see the [vCD API documentation on AMQP](https://code.vmware.com/apis/442/vcloud#/doc/doc/types/AmqpSettingsType.html).

### `vcs` Section

Properties in this section supply credentials necessary for the following operations:

* Guest Operation Program Execution
* Guest Operation Modifications
* Guest Operation Queries

Each `vc` under the `vcs` section has the following properties:

| Property | Value                                                                             |
|----------|-----------------------------------------------------------------------------------|
| name     | Name of the vCenter as registered in vCD                                          |
| username | User name of the vCenter service account with at least guest-operation privileges |
| password | Password of the vCenter service account                                           |

Note : All VCs registered in vCD must be listed here, otherwise CSE server
installation will fail during pre-check phase.

<a name="service_section"></a>
### `service` Section

The service section contains properties that define CSE server behavior.

| Property              | Value                                                                                                                                                      |
|-----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| listeners             | Number of threads that CSE server should use                                                                                                               |
| enforce_authorization | If True, CSE server will use role-based access control, where users without the correct CSE right will not be able to deploy clusters (Added in CSE 1.2.6) |
| log_wire              | If True, will log all REST calls initiated by CSE to vCD. (Added in CSE 2.5.0)                                                                             |
| telemetry             | If enabled, will send back anonymized usage data back to VMware (Added in CSE 2.6.0)                                                                       |

<a name="broker"></a>
### `broker` Section

The `broker` section contains properties to define resources used by
the CSE server including org and VDC as well as template repository location.
The following table summarizes key parameters.

| Property                     | Value                                                                                                                                                                                                                |
|------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| catalog                      | Publicly shared catalog within `org` where K8s templates will be stored                                                                                                                                              |
| default_template_name        | Name of the default template to use if one is not specified during cluster and node operations. CSE server won't start up if this value is invalid. (Added in CSE 2.5.0)                                             |
| default_template_revision    | Revision of the default template to use if one is not is specified during cluster and node operations. CSE server won't start up if this value is invalid. (Added in CSE 2.5.0)                                      |
| ip_allocation_mode           | IP allocation mode to be used during the install process to build the template. Possible values are `dhcp` or `pool`. During creation of clusters for tenants, `pool` IP allocation mode is always used              |
| network                      | Org Network within `vdc` that will be used during the install process to build the template. It should have outbound access to the public Internet. The `CSE` appliance doesn't need to be connected to this network |
| org                          | vCD organization that contains the shared catalog where the K8s templates will be stored                                                                                                                             |
| remote_template_cookbook_url | URL of the template repository where all template definitions and associated script files are hosted. (Added in CSE 2.5.0)                                                                                           |
| storage_profile              | Name of the storage profile to use when creating the temporary vApp used to build the template                                                                                                                       |
| vdc                          | Virtual data-center within `org` that will be used during the install process to build the template                                                                                                                  |

<a name="templte_rules"></a>
### `template_rules` Section
#### (Added in CSE 2.5.0)

Rules can be created to override some of the default attributes of templates
defined by the remote template repository.

This section can contain zero or more such rules, each rule matches exactly one
template. Matching is driven by name and revision of the template. If only name
is specified without the revision or vice versa, the rule will not be
processed.

Each rule comprises of the following attributes

| Property | Value                                                                                                            |
|--------  |------------------------------------------------------------------------------------------------------------------|
| name     | Name of the rule                                                                                                 |
| target   | Name and revision of the template on which the rule will be applied                                              |
| action   | Template properties that will be overridden. Only supported properties are `compute_policy`, `cpu`, and `memory` |

Please refer to [Restricting Kubernetes templates](/container-service-extension/TEMPLATE_MANAGEMENT.html#restrict_templates)
for further details on compute policies.

<a name="ent_pks_config"></a>
## Enterprise PKS Configuration File for CSE
Sample Enterprise PKS configuration file for CSE can be generated via the
following command

```sh
cse sample --pks-config -o pks.yaml
```

Edit this file to add values from your Enterprise PKS installation. The
following example shows a file with sample values filled out.

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
  - vsphere-cluster-1
  - vsphere-cluster-2
  - vsphere-cluster-3
  cpi: cpi1
  datacenter: pks-s1-dc
  host: pks-api-server-1.pks.local
  name: pks-api-server-1
  port: '9021'
  uaac_port: '8443'
  vc: vc1
  verify: true
- clusters:
  - vSphereCluster-1
  - vSphereCluster-2
  - vSphereCluster-3
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
- cluster: vsphere-cluster-1
  name: pvdc1
  pks_api_server: pks-api-server-1
- cluster: vsphere-cluster-1
  name: pvdc2
  pks_api_server: pks-api-server-2
- cluster: vsphere-cluster-4
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

<a name="encrypt_decrypt"></a>
## Encryption and Decryption of the Configuration Files
Starting with CSE 2.6.0, CSE server commands will accept only encrypted
configuration files by default. As of now, these are CSE configuration file and
Enterprise PKS configuration file. CSE exposes two server CLI commands to help
CSE server administrators encrypt and decrypt the configuration files.

```sh
cse encrypt config.yaml --output encrypted-config.yaml
cse decrypt encrypted-config.yaml -o decrypted-config.yaml
```

CSE uses industry standard symmetric encryption algorithm [Fernet](https://cryptography.io/en/latest/fernet/)
and the encryption is dependent on user provided passwords. It is imperative that
CSE server administrators who participate in the encryption process do not lose
the password under any circumstances. CSE will not be able to recover the
password or permit decryption in such cases. CSE expects all configuration files
to be encrypted with the same password.

Whenever an encrypted configuration file is used with CSE server CLI commands,
CSE will prompt the user to provide the password to decrypt them. User can also
propagate the password to CSE via the environment variable `CSE_CONFIG_PASSWORD`.

The default behavior can be changed to keep CSE Server accept plain text
configuration files using the flag `--skip-config-decryption` with any CSE
command that accepts a configuration file. 

