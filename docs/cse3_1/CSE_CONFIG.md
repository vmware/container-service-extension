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

The output of the command varies slightly depending whether the flag `--legacy-mode`
has been used with the command or not.

If the flag is omitted, sample for `MQTT` bus type is generated, otherwise `AMQP` bus type sample is generated.
It should be noted that VCD 10.1 can only support `AMQP` bus. VCD 10.2 and 10.3 will default to `MQTT` if the
`legacy-mode` flag is omitted, otherwise they will be forced to use `AMQP` as the bus.

Edit this file to add values from your VMware Cloud Director installation. The
following example shows a file with sample values filled out.

```yaml
# Only one of the amqp or mqtt sections should be present.

#amqp:
#  exchange: cse-ext
#  host: amqp.vmware.com
#  password: guest
#  port: 5672
#  prefix: vcd
#  routing_key: cse
#  username: guest
#  vhost: /

mqtt:
  verify_ssl: true

vcd:
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
  legacy_mode: false
  log_wire: false
  no_vc_communication_mode: false
  processors: 15
  telemetry:
    enable: true

broker:
  catalog: cse
# default_template_name: my_template
# default_template_revision: 0
  ip_allocation_mode: pool
  network: my_network
  org: my_org
  remote_template_cookbook_url: https://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template_v2.yaml
  storage_profile: '*'
  vdc: my_org_vdc
```

The config file has 4 mandatory sections ( [`amqp` | `mqtt`], `vcd`,
`service`, and, `broker`) and 2 optional section(`vcs`, `template_rules`). The
following sub-sections explain the configuration properties for each section
as well as how they are used.

### `vcd` Section

This section contains the standard information for CSE server to connect to
the VCD server.

<a name="api_version"></a>
Starting CSE 3.1, it is no longer needed to start CSE with a 
particular VCD API version. As a side effect, CSE 3.1 will not recognize `api_version` 
property under `vcd` section of the config file. This property can be safely deleted 
from the existing configuration files.

### `amqp` Section

During CSE Server installation, CSE will set up AMQP to ensure
communication between VCD and the running CSE server. The `amqp`
section controls the AMQP communication parameters. The following
properties will need to be set for all deployments.

| Property | Value                                                                                              |
|----------|----------------------------------------------------------------------------------------------------|
| exchange | Exchange name unique to CSE (CSE will create and use this exchange to communicate with VCD)        |
| host     | IP or hostname of the VMware Cloud Director AMQP server (may be different from the VCD cell hosts) |
| username | AMQP username                                                                                      |
| password | AMQP password                                                                                      |

Other properties may be left as is or edited to match site conventions.

For more information on AMQP settings, see the [VCD API documentation on AMQP](https://code.vmware.com/apis/442/vcloud#/doc/doc/types/AmqpSettingsType.html).

**Note** : When CSE 3.1 is configured in non `legacy_mode`, AMQP is not supported. MQTT must be used.

<a name="mqtt_section"></a>
### `mqtt` Section

Starting CSE 3.0.1, CSE will support MQTT message buses for communication with
vCD. The minimum VCD version required is 10.2. During CSE installation phase,
CSE will setup the MQTT exchange. During CSE upgrades, CSE can switch over from
AMQP to MQTT, however the reverse is not permitted.

| Property   | Value                                                              |
|------------|--------------------------------------------------------------------|
| verify_ssl | verify ssl certificates while communicating with the MQTT exchange |

<a name="mqtt"></a>
**Note** : When CSE 3.1 is configured in `legacy_mode`, MQTT is not supported.
Additionally, it is strongly recommended to use MQTT if working with VCD 10.3 or 10.2.

### `vcs` Section (Made optional in CSE 3.1.1)

Properties in this section supply credentials necessary for the following operations:

* Guest Operation Program Execution
* Guest Operation Modifications
* Guest Operation Queries

Each `vc` under the `vcs` section has the following properties:

| Property | Value                                                                             |
|----------|-----------------------------------------------------------------------------------|
| name     | Name of the vCenter as registered in VCD                                          |
| username | User name of the vCenter service account with at least guest-operation privileges |
| password | Password of the vCenter service account                                           |

**Note** : If `no_vc_communication_mode` is set to `False`, all vCenter servers registered with
VCD must be listed here, otherwise CSE server installation/startup will fail during pre-check phase.
However if `no_vc_communication_mode` is set to `True`, the entire `vcs` section can be omitted.

<a name="service_section"></a>
### `service` Section

The service section contains properties that define CSE server behavior.

| Property                 | Value                                                                                                                                 | Remarks              |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------|----------------------|
| listeners                | Number of threads that CSE server should use to communicate with AMQP bus and process requests                                        | Removed in CSE 3.0.1 |
| processors               | Number of threads that CSE server should use for processing requests                                                                  | Added in CSE 3.0.1   |
| enforce_authorization    | If True, CSE server will use role-based access control, where users without the correct CSE right will not be able to deploy clusters | Added in CSE 1.2.6   |
| log_wire                 | If True, will log all REST calls initiated by CSE to VCD.                                                                             | Added in CSE 2.5.0   |
| telemetry                | If enabled, will send back anonymized usage data back to VMware                                                                       | Added in CSE 2.6.0   |
| legacy_mode              | Need to be True if CSE >= 3.1 is configured with VCD <= 10.1                                                                          | Added in CSE 3.1.0   |
| no_vc_communication_mode | If set to True, CSE will not communicate with vCenter servers regitered with VCD                                                      | Added in CSE 3.1.1   |

<a name="no_vc_communication_mode"></a>
**CSE 3.1.1 - new property - `no_vc_communication_mode`:**
Starting CSE 3.1.1, new property `no_vc_communication_mode` has been added. This property indicates whether CSE server 
should communicate with vCenter servers or not while managing life cycle of clusters.
   * set the `no_vc_communication_mode` to true, if vCenter servers can't be accessed from CSE server. Such a setup can be used for TKG cluster deployments only.
   * set the `no_vc_communication_mode` to false if CSE server has access to the vCenter servers. For native cluster deployments this is mandatory.

<a name="legacy_mode"></a>
**CSE 3.1.0 - new property - `legacy_mode`:**
Starting CSE 3.1.0, new property `legacy_mode` has been added. This property indicates whether CSE server 
needs to leverage the latest features of VCD like RDE framework, placement policies or not.
   * set the `legacy_mode` to true if CSE 3.1 is configured with VCD 10.1. 
     Native clusters are nothing but regular vApps with some Kubernetes specific metadata.
   * set the `legacy_mode` to false if CSE 3.1 is configured with VCD >= 10.2. 
     Native clusters are represented in the form of RDEs powered by vApps.

<a name="broker"></a>
### `broker` Section

The `broker` section contains properties to define resources used by
the CSE server including org and VDC as well as template repository location.
The following table summarizes key parameters.

| Property                     | Value                                                                                                                                                                                                                 | Remarks                                  |
|------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------|
| catalog                      | Publicly shared catalog within `org` where K8s templates will be stored.                                                                                                                                              |                                          |
| default_template_name        | Name of the default template to use if one is not specified during cluster and node operations. CSE server won't start up if this value is invalid.                                                                   | Added in CSE 2.5.0, Removed in CSE 3.1.1 |
| default_template_revision    | Revision of the default template to use if one is not is specified during cluster and node operations. CSE server won't start up if this value is invalid.                                                            | Added in CSE 2.5.0, Removed in CSE 3.1.1 |
| ip_allocation_mode           | IP allocation mode to be used during the install process to build the template. Possible values are `dhcp` or `pool`. During creation of clusters for tenants, `pool` IP allocation mode is always used.              |                                          |
| network                      | Org Network within `vdc` that will be used during the install process to build the template. It should have outbound access to the public Internet. The `CSE` appliance doesn't need to be connected to this network. |                                          |
| org                          | VCD organization that contains the shared catalog where the K8s templates will be stored.                                                                                                                             |                                          |
| remote_template_cookbook_url | URL of the template repository where all template definitions and associated script files are hosted.                                                                                                                 | Added in CSE 2.5.0                       |
| storage_profile              | Name of the storage profile to use when creating the temporary vApp used to build the template.                                                                                                                       |                                          |
| vdc                          | Virtual data-center within `org` that will be used during the install process to build the template.                                                                                                                  |                                          |

**CSE 3.1.1 - removed fields `default_template_name` and `default_template_revision`:**
CSE no longer requires native template(s) to be present for startup. As a result, every
cluster deployment command from user must contain the
template name and revision they wish to use for the deployment.

<a name="template_cookbook_20"></a>
**CSE 3.1.0 - new template cookbook 2.0:**
For the `remote_template_cookbook_url` property, CSE 3.1 `config.yaml` must refer
to `http://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template_v2.yaml`. 
CSE <= 3.0 will not work with the new template cookbook 2.0. When `legacy_mode` is set to true, 
`remote_template_cookbook_url` of CSE 3.1 `config.yaml` must refer to old template cookbook 
`https://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template.yaml`.

<a name="templte_rules"></a>
### `template_rules` Section (Added in CSE 2.5.0, Deprecated in CSE 3.0.0)

**Note** : `template_rules` section is not applicable when CSE 3.1 is configured in `non_legcay` mode

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

Please refer to [Restricting Kubernetes templates](TEMPLATE_MANAGEMENT.html#restrict_templates)
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
#          vCenter is registered in VCD.
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
#       a. Each entry in the list represents a Provider VDC in VCD that is
#          backed by a cluster of the Enterprise PKS managed vCenter server.
#       b. The field 'name' in each entry should be the name of the
#          Provider VDC as it appears in VCD.
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

