---
layout: default
title: CSE Server Installation Prerequisites
---
# CSE Server Installation Prerequisites

<a name="prerequisites"></a>
## vCD Prerequisites

There are several important requirements that must be fulfilled to install
CSE successfully on vCD.

* An org.
* A VDC within the org, which
  * has an org VDC network connected to an external network (with Internet connectivity). The external network connection is required to enable cluster VMs to download packages during configuration.
  * can host vApps
  * has sufficient storage to create vApps and publish them as templates.
* Users in the org with privileges necessary to perform operations like configuring AMQP, creating public catalog entries, and managing vApps.
* A good network connectivity between the machine where CSE is installed and the vCD server as well as the Internet.  This avoids intermittent failures in OVA upload/download operations.

You can use existing resources from your vCD installation or create
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
# 'Corporate' external network already exists in vCD.
vcd vdc use cse_vdc_1
vcd network direct create CSE_org_vdc_network \
  --description 'Internet facing network' \
  --parent 'Corporate' \
  --shared
```

### CSE User

We recommend using a vCD System admin account for CSE server management.
