---
layout: default
title: Known Issues
---
# Known Issues

<a name="general"></a>
## General Problems

### Failures during template creation or installation
- One of the template-creation scripts may have exited with an error
- One of the scripts may be hung waiting for a response
- If the VM has no internet access, scripts may fail
- Check CSE logs for script outputs

### CSE service fails to start
- Workaround: rebooting the VM starts the service

### CSE does not clean up after itself if something goes wrong. 

When CSE installation is aborted for any reason, ensure temporary vApp is deleted in vCD before re-issuing the install command
- Manually delete the problematic "ubuntu-temp" vApp.
- If temporary vApp still exists and `cse install` command is run again, CSE will just capture the vApp as the Kubernetes template, even though the vApp is not set up properly.
- Running CSE install with the `--update` option will remove this invalid vApp.

### CSE v1.1.x compatibility with vCD 8.20 requires the following package versions
- pyvcloud 19.3.0
- vcd_cli 20.3.0

### CSE 1.2.x is incompatible with vCD 9.0
- CSE installation fails with MissingLinkException

<a name="nfs"></a>
## NFS Limitations

Currently, NFS servers in a Kubernetes cluster are not only accessible
by nodes of that cluster but also by any VM (outside of the cluster)
residing in the same orgVdc. Ideal solution is to have vApp network
created for each Kubernetes cluster, which is in our road-map to
implement. Until then, please choose one of below workarounds to
avert this problem if the need arises.

- Give access to only master & worker nodes of the cluster by adding individual IPs of the nodes into /etc/exports file on NFS server.
    - Create and run a script periodically which retrieves IPs of nodes in the cluster and then add them to NFS server access list (/etc/exports).
    - eg: /home 203.0.113.256(rw,sync,no_root_squash,no_subtree_check) 203.0.113.257(rw,sync,no_root_squash,no_subtree_check)
- Admin can manually add a vApp network for each kubernetes cluster in vCD.
- Create a ssh tunnel from each worker node (using ssh local port forwarding) and then use 127.0.0.1:<port> in the  Kubernetes declarative specs as IP of the NFS server.
    - In NFS server, for any given shared directory, add below line to /etc/exports file.
        - /home localhost(insecure,rw,sync,no_subtree_check)
        - systemctl restart nfs-kernel-server.service
    - Copy ssh public key of each worker node into ~/.ssh/authorized_keys in NFS server
        - Client: Generate key using ssh-keygen and copy the contents of ~/.ssh/id_rsa.pub
        - NFS server: Paste the contents (public key) from client into ~/.ssh/authorized_keys
    - In each master/worker node,
        - apt-get install portmap
        - ssh -fNv -L 3049:127.0.0.1:2049 user@NFSServer
    - Read more about this approach here
        - http://www.debianadmin.com/howto-use-ssh-local-and-remote-port-forwarding.html
        - https://gist.github.com/proudlygeek/5721498

