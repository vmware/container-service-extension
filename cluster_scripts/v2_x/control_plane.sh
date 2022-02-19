#!/usr/bin/env bash
set -e
tkg_plus_kind="TKG+"
input_kind="{cluster_kind}"
kubeadm_config_path=/root/kubeadm-defaults.conf

while [ `systemctl is-active docker` != 'active' ]; do echo 'waiting for docker'; sleep 5; done
if [ "$input_kind" == "$tkg_plus_kind" ]; then
    # use kubeadm config if TKG plus cluster
    kubeadm init --config=$kubeadm_config_path > /root/kubeadm-init.out
else
    if [[ "$(lsb_release -rs)" =~ "20.04" ]]; then
        # if os is ubuntu 20.04, then use containerd cri-socket
        kubeadm init --kubernetes-version=v{k8s_version} --cri-socket=/run/containerd/containerd.sock > /root/kubeadm-init.out
    else
        kubeadm init --kubernetes-version=v{k8s_version} > /root/kubeadm-init.out
    fi
fi

mkdir -p /root/.kube
cp -f /etc/kubernetes/admin.conf /root/.kube/config
chown $(id -u):$(id -g) /root/.kube/config

export kubever=$(kubectl version --client | base64 | tr -d '\n')

WEAVE_VERSIONED_FILE="/root/weave_v$(echo {cni_version} | sed -r 's/\./\-/g').yml"
kubectl apply -f $WEAVE_VERSIONED_FILE
systemctl restart kubelet
while [ `systemctl is-active kubelet` != 'active' ]; do echo 'waiting for kubelet'; sleep 5; done
