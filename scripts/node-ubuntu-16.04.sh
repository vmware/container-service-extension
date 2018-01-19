#!/usr/bin/env bash
set -e
while [ `systemctl is-active docker` != 'active' ]; do echo 'waiting for docker'; sleep 5; done
kubeadm join --token {token} {ip}:6443 --discovery-token-unsafe-skip-ca-verification
