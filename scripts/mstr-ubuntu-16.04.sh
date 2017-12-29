#!/usr/bin/env bash

while [ `systemctl is-active docker` != 'active' ]; do systemctl is-active docker; sleep 5; done
kubeadm init --kubernetes-version=v1.8.2 > /root/kubeadm-init.out
mkdir -p /root/.kube
cp -f /etc/kubernetes/admin.conf /root/.kube/config
chown $(id -u):$(id -g) /root/.kube/config
kubectl apply -f /root/weave.yml
