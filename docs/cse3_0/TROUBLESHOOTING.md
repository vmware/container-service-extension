---
layout: default
title: Troubleshooting
---
<a name="cse30-faq"></a>
# CSE 3.0 FAQ

## Admin operations
1. Is CSE 3.0 backward compatible? In other words, does it work with older API 
versions of Cloud Director (<= 34.0)?
    * Yes. CSE Server 3.0, when connected with Cloud Director of API versions <= 34.0, 
    will continue to behave as CSE 2.6.x. For accurate results, follow the 
    [compatibility matrix](CSE30.html#cse30-compatibility-matrix)
2. How do placement policies work? What is their relationship with ovdc enablement and template restriction?
    * CSE 3.0, when connected to VCD >= 10.2, leverages the concept of placement 
    policies to restrict native K8 deployments to specific organization virtual 
    datacenters. During CSE install or upgrade, it creates an empty provider 
    Vdc level placement policy **cse----native** and tags the native templates 
    with the same. In effect, one can instantiate VM(s) from (**cse----native** tagged)
    templates only in those ovdc(s) with the placement policy **cse----native** published.
        1. (provider command) `cse install` or `cse upgrade` creates native 
        placement policy **cse----native** and tags the relevant templates with
         the same placement policy.
        2. (provider command) `vcd cse ovdc enable` publishes the native 
        placement policy on to the chosen ovdc.
        3. (tenant command) `vcd cse cluster apply` - During the cluster creation,
        VCD internally validates the ovdc eligibility to host the cluster VMs 
        instantiated from the native templates, by checking if the template's 
        placement policy is published onto the ovdc or not.
    * Note that CSE 3.0, when connected to VCD < 10.2, will continue to behave as 
    CSE 2.6 in terms of [template restriction](TEMPLATE_MANAGEMENT.html#restrict_templates).
3. What does it mean for CSE server to be running at a certain vCD API version?
    * CSE server uses the api version (vcd->api_version) specified in the `config.yaml` to communicate to vCD. 
    * For example: With CSE server connected to vCD 10.2, if the `api_version`
     specified in the `config.yaml` is 34.0, then CSE server is said to be 
     running at `api_version` 34.0, even though the maximum supported `api_version`
      of vCD 10.2 is 35.0. Admin(s) need to update the `config.yaml` with the 
      desired api_version they want CSE server to communicate with Cloud Director.
4. Where do I read more about runtime defined entities and relevant API?
    * [Runtime defined entities](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-0749DEA0-08A2-4F32-BDD7-D16869578F96.html)
<a name="sync-def-entity"></a>
5. If defined entity representation seems to be stale or out of sync with the actual state of the backing cluster vApp, how to sync the defined entity status?
    * Invoke an API call to the CSE server from postman - GET on `https://<vcd-ip>/api/cse/3.0/clusters/<id>`
6. Can providers provide Certificates during CSE installation and startup?
    * Customers can provide the path to their CA Bundle and set the REQUESTS_CA_BUNDLE environment variable with the provided path. This has been tested on Mac OS.
7. With CSE 3.0 - vCD 10.1 combination, as native clusters are by default allowed to be deployed on any organization virtual datacenters, how can we prevent native clusters from getting deployed on Ent-PKS enbled ovdc(s)?
    * Use template rules to protect native templates. Refer [CSE 2.6 template restriction](TEMPLATE_MANAGEMENT.html#restrict_templates).
     
## Tenant operations

1. Can Native and TKG clusters be deployed in the same organizational virtual datacenter?
    * Yes. As long as the given virtual datacenter is enabled for both native & tkg, and virtual datacenter network intended for native has internet connectivity, users should be able to deploy both native and tkg clusters in the same organization virtual datacenter (ovdc).
2. Can Native, TKG and Ent-PKS be deployed in the same organizational virtual datacenter?
    * No. Ent-PKS requires dedicated virtual datacenter.
3. Are Ent-PKS clusters represented as Runtime defined entities in CSE 3.0?
    * No.
4. What are the steps to share a cluster with other tenant users?
    * Native
        * Share the backing vApp to the desired users. 
        * [Share the defined entity](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-DAFF4CE9-B276-4A0B-99D9-22B985153236.html).
    * Tkg
        * [Share the defined entity](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-DAFF4CE9-B276-4A0B-99D9-22B985153236.html)
5. Is heterogeneity in Native cluster nodes supported? In other words, can nodes of different sizes and shapes exist in a given cluster?
    * No. The specification provided during cluster creation will be used throughout the life cycle management of the cluster. For example, worker_storage_profile specified during the cluster creation step will be used for further resize operations.
6. Are scale-up and down operations supported for native and tkg clusters?
    * Yes.
7. Is scale-down supported for the NFS nodes of the native clusters via `vcd cse cluster apply` command?
    * No. One has to use `vcd cse cluster delete-nfs <cluster-name> <nfs-node-name>` command to delete a given NFS node.
<a name="cmds-per-cse"></a>
8. What commands are functional for what CSE api_version?
    *  
| After `vcd login` &  CSE api_version >= 35.0                                                                                                                                                                                                                                | After `vcd login` &  CSE api_version < 35.0                                                                                                                                                                                                                     | After `vcd login` &  vCD api_version >= 35.0 &  CSE Server is down                                                                                                                                                                       | Before `vcd login`                                                                                                  |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| `vcd cse cluster apply` <br />  `vcd cse cluster upgrade` <br />  `vcd cse cluster delete` <br />  `vcd cse cluster delete-nfs` <br />  `vcd cse cluster upgrade-plan` <br />  `vcd cse cluster config` <br />  `vcd cse cluster list` <br />  `vcd cse cluster info`<br /> | `vcd cse cluster create` <br /> `vcd cse cluster resize` <br />  `vcd cse cluster delete` <br />  `vcd cse cluster upgrade` <br /> `vcd cse cluster upgrade-plan` <br /> `vcd cse cluster config` <br />  `vcd cse cluster list` <br />  `vcd cse cluster info` | Commands can be used to operate TKG clusters only<br />    `vcd cse cluster apply` <br /> `vcd cse cluster upgrade` <br /> `vcd cse cluster delete` <br /> `vcd cse cluster config` <br /> `vcd cse cluster list` <br />  `vcd cse cluster info` | Union of all commands are displayed on running vcd cse --help. Login is required for the commands to be functional. |
| All node operations  can be performed through    `vcd cse cluster apply`                                                                                                                                                                                                    | `vcd cse node info` <br />  `vcd cse node list` <br />  `vcd cse node add` <br />  `vcd cse node delete`                                                                                                                                                        |                                                                                                                                                                                                                                                  |                                                                                                                     |
| `vcd cse ovdc enable` <br />`vcd cse ovdc disable`  <br />  `vcd cse ovdc list`                                                                                                                                                                                             | `vcd cse ovdc compute-policy`                                                                                                                                                                                                                                   |                                                                                                                                                                                                                                                  |                                                                                                                     |
| `vcd cse pks *`                                                                                                                                                                                                                                                             | `vcd cse pks *`                                                                                                                                                                                                                                                 |                                                                                                                                                                                                                                                  |                                                                                                                     |
| `vcd cse template *`                                                                                                                                                                                                                                                        | `vcd cse template *`                                                                                                                                                                                                                                            |                                                                                                                                                                                                                                                  |                                                                                                                     |

<a name="log-bundles"></a>
# Log Bundles
Logs are stored under the folder `.cse-logs` in the home directory

* `cse-install_[datetimestamp].log` logs CSE install activity. Any output from
scripts or error messages during CSE installation, CSE upgrade or
template installation will be logged here.
* `cse-install-wire_[datetimestamp].log` logs all server requests and responses
originating from CSE during CSE install, CSE upgrade or template install activity.
This file is generated only if the `log_wire` field under `service` section of
config file is set to `true`.
* `cse-server-debug.log`, `cse-server-info.log` logs CSE server's activity.
Server requests and responses are recorded here, as well as outputs of scripts
that were run on VMs.
* `cse-server-wire-debug.log` logs all REST calls originating from CSE to VCD.
This file is generated only if the `log_wire` field under `service` section of
config file is set to `true`.
* `cse-server-cli.log` logs all the CSE server CLI activity. CSE server
commands that are executed, the outputs and debugging information are recorded
here.
* `cse-server-cli-wire.log` logs all the requests and responses originated
from CSE while executing the CSE server CLI commands. This file is generated
only if the `log_wire`  field under `service` section of config file
is set to `true`.
* `nsxt-wire.log` logs all the REST calls originating from CSE server to
NSX-T server. This file is generated only if the `log_wire` field
under `service` section of config file is set to `true`.
* `pks-wire.log` logs all the REST calls originating from CSE server to
PKS API server. This file is generated only if the `log_wire` field
under `service` section of config file is set to `true`.
* `cloudapi-wire.log` logs all the CloudAPI REST calls made to VCD.
This file is generated only if the `log_wire` field under `service` section of
config file is set to `true`.
* `cse-client-info.log`, `cse-client-debug.log` logs CSE client CLI activities.
Requests made to CSE server, their responses and debugging information
are recorded here.
* `cse-client-wire.log` logs all REST calls originating from CSE CLI client to
CSE server. This file is generated only if the environment variable
`CSE_CLIENT_WIRE_LOGGING` is set to `true`.

VCD CLI logs can be found in the path where the command was executed.

* `vcd.log`, `vcd_cli_error.log` log vcd-cli and pyvcloud activity on client
side. Stack traces and HTTP messages specific to vcd-cli are recorded here.

## Common errors to look out for

* Ensure that config file fields are correct
* Ensure you're logged in using vcd-cli
* Ensure that the AMQP exchange specified in CSE config file is unique. Do not use the exchange specified in VCD's extensibility section for CSE. As long as a uniquely-named exchange is specified in the CSE config file, CSE will create that exchange and use it to communicate with VCD. No changes needs to be made in VCD's extensibility section or in RabbitMQ.
* If CSE installation or template creation fails, invalid VMs/clusters/templates may exist. CSE can't auto detect that those entities are invalid, so remove these entities from VCD manually.
