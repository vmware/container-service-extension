#!/usr/bin/env bash
set -e

is_tkgm={is_tkgm}
kubeadm_config_path=/root/kubeadm-defaults-join.conf

while [ `systemctl is-active docker` != 'active' ]
do
  echo 'waiting for docker'
  sleep 5
done

if [ "$is_tkgm" = true ]; then
  sed -i 's/IP_PORT/{ip_port}/; s/DISCOVERY_TOKEN_CA_CERT_HASH/{discovery_token_ca_cert_hash}/' $kubeadm_config_path
  kubeadm join --config=$kubeadm_config_path
else
  kubeadm join {ip_port} --token {token} --discovery-token-ca-cert-hash {discovery_token_ca_cert_hash}
fi
