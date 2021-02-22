#!/usr/bin/env bash
set -e

while [ `systemctl is-active docker` != 'active' ]
do
  echo 'waiting for docker'
  sleep 5
done

kubeadm join {ip_port} --token {token} --discovery-token-ca-cert-hash {discovery_token_ca_cert_hash}

