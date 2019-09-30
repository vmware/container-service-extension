---
layout: default
title: Troubleshooting
---
# TroubleShooting

`cse-server-debug.log`, `cse-server-info.log` logs CSE Server activity. Server requests and responses are recorded here, as well as outputs of scripts that were run on VMs.

`cse-install_[datetimestamp].log` logs CSE install activity. Any output from scripts or error messages during CSE installation will be logged here.

`cse-install-wire_[datetimestamp].log` logs all server requests and responses originating from CSE during install activity. This file is generated only if the `log_wire` field under services section of config file is true.

`cse-server-wire-debug.log` logs all REST calls originating in CSE for vCD.

`vcd.log`, `vcd_cli_error.log` log vcd-cli and pyvcloud activity on client side. Stack traces and HTTP messages specific to vcd-cli are recorded here.

Common mistakes:
- Config file fields are incorrect
- Not logged in to vCD via vcd-cli
- Logged in to vCD via vcd-cli as wrong user or user without required permissions
- Config file and vCD should have same host/exchange, and make sure exchange exists on vCD
    - On server start, monitor with `tail -f cse-server-debug.log`
- If CSE installation/updates failed, broken VMs/clusters/templates may exist, and CSE will not know that entities are invalid.
    - Remove these entities from vCD manually
