#!/usr/bin/env bash
set -e

systemctl enable nfs-server.service
systemctl start nfs-server.service
echo '/home *(rw,sync,no_root_squash,no_subtree_check)' >> /etc/exports
systemctl restart nfs-server.service
