#!/usr/bin/env bash
set -e

is_tkgm={is_tkgm}

while [ `systemctl is-active docker` != 'active' ]
do
  echo 'waiting for docker'
  sleep 5
done

if [ "$is_tkgm" = true ]; then
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
    kubeletExtraArgs:
      cloud-provider: external
  " > /root/kubeadm-defaults-join.conf
  kubeadm join --config /root/kubeadm-defaults-join.conf
else
  kubeadm join {ip_port} --token {token} --discovery-token-ca-cert-hash {discovery_token_ca_cert_hash}
fi
