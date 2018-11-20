#!/usr/bin/env bash
set -e

### Uncomment if you want to enable root password access
### root password access is dangerous; ssh-key access is recommended
# sed -i 's/prohibit-password/yes/' /etc/ssh/sshd_config

sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
apt remove -y cloud-init
dpkg-reconfigure openssh-server
sync
sync
