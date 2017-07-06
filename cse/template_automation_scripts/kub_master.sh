#!/bin/bash -eux

/usr/bin/tdnf -y install kubernetes
iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT
iptables -P FORWARD ACCEPT
chown -R kube:kube /run
