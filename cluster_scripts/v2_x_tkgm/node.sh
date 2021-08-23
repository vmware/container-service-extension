#!/usr/bin/env bash
set -e

kubeadm_config_path=/root/kubeadm-defaults-join.conf

echo "---
apiVersion: kubeadm.k8s.io/v1beta2
kind: JoinConfiguration
caCertPath: /etc/kubernetes/pki/ca.crt
discovery:
  bootstrapToken:
    apiServerEndpoint: {ip_port}
    token: {token}
    unsafeSkipCAVerification: false
    caCertHashes: [{discovery_token_ca_cert_hash}]
  timeout: 5m0s
nodeRegistration:
  criSocket: /run/containerd/containerd.sock
  kubeletExtraArgs:
    cloud-provider: external
" > /root/kubeadm-defaults-join.conf

kubeadm join --config $kubeadm_config_path
