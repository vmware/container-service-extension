#!/usr/bin/env bash
sed -i 's/prohibit-password/yes/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
apt remove -y cloud-init
dpkg-reconfigure openssh-server
sync
sync
