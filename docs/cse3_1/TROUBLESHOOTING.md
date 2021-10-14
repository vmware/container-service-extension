---
layout: default
title: Troubleshooting
---
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
* Ensure that the AMQP exchange specified in CSE config file is unique.
Do not use the exchange specified in VCD's extensibility section for CSE.
As long as a uniquely-named exchange is specified in the CSE config file,
CSE will create that exchange and use it to communicate with VCD.
No changes needs to be made in VCD's extensibility section or in RabbitMQ.
* If CSE installation or template creation fails, invalid VMs/clusters/templates
may exist. CSE can't auto detect that those entities are invalid, so remove
these entities from VCD manually.
