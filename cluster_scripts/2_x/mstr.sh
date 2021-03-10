#!/usr/bin/env bash
set -ex

while [ `systemctl is-active docker` != 'active' ]
do
  echo 'waiting for docker'
  sleep 5
done

cat << EOF > /lib/systemd/system/kubelet.service
# This file was added by the Container Service Extension team at VMware.
# Note: This dropin only works with kubeadm and kubelet v1.11+
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

kubeadm init --kubernetes-version=v{k8s_version} > /root/kubeadm-init.out

mkdir -p /root/.kube
cp -f /etc/kubernetes/admin.conf /root/.kube/config
chown $(id -u):$(id -g) /root/.kube/config

export kubever=$(kubectl version --client | base64 | tr -d '\n')

# BUG: This download should actually be performed by the template scripts.
wget --no-verbose -O /root/weave.yml "https://cloud.weave.works/k8s/net?k8s-version=$kubever&v={cni_version}"

kubectl apply -f /root/weave.yml

exit 0
