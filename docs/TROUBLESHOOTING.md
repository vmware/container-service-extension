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

Common mistakes:
* Config file fields are incorrect.
* Not logged in to vCD via vcd-cli.
* Logged in to vCD via vcd-cli as wrong user or user without required permissions.
* AMQP exchange mentioned in config file should be the same one that vCD is
using. CSE should have it's own dedicated exchange and not use vCD's default
extension exchange.
* If CSE installation/updates failed, broken VMs/clusters/templates may exist.
CSE can't auto detect that those entities are invalid.
    * Remove these entities from vCD manually.
