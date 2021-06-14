---
layout: default
title: CSE Server Installation Prerequisites
---
# CSE Server Installation Prerequisites

<a name="prerequisites"></a>
## VCD Prerequisites

There are several important requirements that must be fulfilled to install
CSE successfully on VCD.

* An org.
* A VDC within the org, which
  * has an org VDC network connected to an external network (with Internet connectivity). The external network connection is required to enable cluster VMs to download packages during configuration.
  * can host vApps
  * has sufficient storage to create vApps and publish them as templates.
* Users in the org with privileges necessary to perform operations like configuring AMQP, creating public catalog entries, and managing vApps.
* A good network connectivity between the machine where CSE is installed and the VCD server as well as the Internet.  This avoids intermittent failures in OVA upload/download operations.

You can use existing resources from your VCD installation or create
new ones. The following sub-sections illustrate how to set up a
suitable org + VDC + user from scratch.

### Create an Org

Use the UI or vcd-cli to create an org for CSE use.

```sh
vcd org create --enabled cse_org_1 'Org for CSE work'
```

### Create a VDC with Attached Network

Next create a VDC that has an org VDC network that can route network traffic
from VMs to the Internet. Here are sample vcd-cli commands.

```sh
# Switch to org and create VDC under it.
vcd org use cse_org_1
vcd vdc create cse_vdc_1 \
  --provider-vdc 'Sample-provider-vdc' \
  --allocation-model 'AllocationVApp' \
  --storage-profile '*' \
  --description 'CSE org VDC'

# Switch to the new VDC and add an outbound network. It's assumed that the
# 'Corporate' external network already exists in VCD.
vcd vdc use cse_vdc_1
vcd network direct create CSE_org_vdc_network \
  --description 'Internet facing network' \
  --parent 'Corporate' \
  --shared
```

<a name="service_account"></a>
### CSE Service Account

We recommend using a user with `CSE Service Role` for CSE server management.
The role comes with all the VCD rights that CSE needs to function. The role
can be created in System organization using the following command.

```sh
cse create-service-role [VCD host fqdn]
```
The command currently supports only VCD 10.2 and later. The command will raise
an error if invoked against an older VCD build. For older vCD builds a user with
`System Administrator` role should be used instead to manage CSE.

Notes:
* The command will prompt for sys admin credentials, and use it to create the Role.
* The command if run more than once will raise an error, since the role already
exists. There is nothing to be concerned about this error though.
* The command will fail with cryptic error message if the VCD server is using
self signed certificates and -s flag is not specified.
