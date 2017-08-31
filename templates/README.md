Creating the vApp template
---

Get latest version of `packer`. This guide assumes `v1.1.0-dev` or newer.

```shell
$ go get github.com/hashicorp/packer
```

The vApp template is created on a ESXi host. See the section at the end for required settings on the host.

Enter the host credentials in the `variables.json` file and run the command:

```shell
$ packer build -var-file variables.json kubernetes-ubuntu.json
```

Download the resulting template from the ESXi host to your local machine. Use `ovftool` to transfer the files.

```shell
$ ovftool 'vi://administrator%40vsphere.local:P%40ssw0rd@esx.vmware.com/DC1?ds=[shared-disk-1]/output-ubuntu-16.04-amd64-vmware-iso/k8s-u.vmx' k8s-u.ova
```

Create a catalog in vCloud Director and shared it with all organizations in the cloud. Use `vcd-cli` as follows:

```shell
$ vcd catalog create cse
catalogCreateCatalog: Created Catalog cse(091912fc-a089-4a02-b1a4-26736ba528fe), status: success
task: 554ab813-af90-488c-8e75-46fe21fe79ed, result: success

$ vcd catalog share cse
Catalog shared.
```

Upload the template to the catalog with `vcd-cli`:

```shell
$ vcd catalog upload cse k8s-u.ova
upload 1,128,098,816 of 1,128,098,816 bytes, 100%
property    value
----------  ----------
file        k8s-u.ova
size        1128106989
```

ESXi Host Configuration
---

In order to create the template with `packer`, ssh to the ESXi host and configure the following settings:

1. GuestIPHack:

```shell
$ esxcli system settings advanced set -o /Net/GuestIPHack -i 1
```

2. Firewall:

```shell
$ chmod 644 /etc/vmware/firewall/service.xml
$ chmod +t /etc/vmware/firewall/service.xml
```

Append the following entry at the end of file `/etc/vmware/firewall/service.xml`:

```xml
<service id="1000">
  <id>packer-vnc</id>
  <rule id="0000">
    <direction>inbound</direction>
    <protocol>tcp</protocol>
    <porttype>dst</porttype>
    <port>
      <begin>5900</begin>
      <end>6000</end>
    </port>
  </rule>
  <enabled>true</enabled>
  <required>true</required>
</service>
```

```shell
$ chmod 444 /etc/vmware/firewall/service.xml
$ esxcli network firewall refresh
```
