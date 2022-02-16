#!/usr/bin/env bash
while [ `systemctl is-active docker` != 'active' ]; do echo 'waiting for docker'; sleep 5; done

lsb_release -a | grep -q 20.04
if [ $? == 0 ]; then
    # if os is ubuntu 20.04, then use containerd cri-socket
    set -e
    kubeadm join {ip_port} --token {token} --discovery-token-ca-cert-hash {discovery_token_ca_cert_hash} --cri-socket=/run/containerd/containerd.sock
else
    set -e
    kubeadm join {ip_port} --token {token} --discovery-token-ca-cert-hash {discovery_token_ca_cert_hash}
fi
