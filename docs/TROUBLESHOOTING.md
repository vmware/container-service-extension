---
layout: default
title: Troubleshooting
---
# TroubleShooting

Logs are stored under the folder `cse-logs`

* `cse-install_[datetimestamp].log` logs CSE install activity. Any output from
scripts or error messages during CSE installation will be logged here.
* `cse-install-wire_[datetimestamp].log` logs all server requests and responses
originating from CSE during install activity. This file is generated only if
the `log_wire` field under `service` section of config file is set to `true`.
* `cse-server-debug.log`, `cse-server-info.log` logs CSE server's activity.
Server requests and responses are recorded here, as well as outputs of scripts
that were run on VMs.
* `cse-server-wire-debug.log` logs all REST calls originating from CSE to vCD.
This file is generated only if the `log_wire` field under `service` section of
config file is set to `true`.
* `vcd.log`, `vcd_cli_error.log` log vcd-cli and pyvcloud activity on client
side. Stack traces and HTTP messages specific to vcd-cli are recorded here.

## Common errors to look out for

* Ensure that config file fields are correct
* Ensure you're logged in using vcd-cli
* Ensure that the AMQP exchange specified in CSE config file is unique. Do not use the exchange specified in vCD's extensibility section for CSE. As long as a uniquely-named exchange is specified in the CSE config file, CSE will create that exchange and use it to communicate with vCD. No changes needs to be made in vCD's extensibility section or in RabbitMQ.
* If CSE installation or template creation fails, invalid VMs/clusters/templates may exist. CSE can't auto detect that those entities are invalid, so remove these entities from vCD manually.
