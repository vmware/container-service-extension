#!/usr/bin/env bash
set -e

systemctl enable nfs-kernel-server.service
systemctl start nfs-kernel-server.service
echo '/home *(rw,sync,no_root_squash,no_subtree_check)' >> /etc/exports
systemctl restart nfs-kernel-server.service