#!/usr/bin/env bash
set -ex

while [ `systemctl is-active docker` != 'active' ]
do
  echo 'waiting for docker'
  sleep 5
done

cat << EOF > /lib/systemd/system/kubelet.service
# This file was added by the Container Service Extension team at VMware.
[Service]
Environment="KUBELET_KUBECONFIG_ARGS=--bootstrap-kubeconfig=/etc/kubernetes/bootstrap-kubelet.conf --kubeconfig=/etc/kubernetes/kubelet.conf"
Environment="KUBELET_CONFIG_ARGS=--config=/var/lib/kubelet/config.yaml"
# This is a file that "kubeadm init" and "kubeadm join" generates at runtime, populating the KUBELET_KUBEADM_ARGS variable dynamically
EnvironmentFile=-/var/lib/kubelet/kubeadm-flags.env
# This is a file that the user can use for overrides of the kubelet args as a last resort. Preferably, the user should use
# the .NodeRegistration.KubeletExtraArgs object in the configuration files instead. KUBELET_EXTRA_ARGS should be sourced from this file.
EnvironmentFile=-/etc/default/kubelet
ExecStart=
ExecStart=/usr/bin/kubelet $KUBELET_KUBECONFIG_ARGS $KUBELET_CONFIG_ARGS $KUBELET_KUBEADM_ARGS $KUBELET_EXTRA_ARGS {cloud_provider_external_args}
EOF

systemctl daemon-reload
systemctl restart kubelet
while [ `systemctl is-active kubelet` != 'active' ]
do
  echo 'waiting for kubelet'
  sleep 5
done

kubeadm join {ip_port} --token {token} --discovery-token-ca-cert-hash {discovery_token_ca_cert_hash}

exit 0
