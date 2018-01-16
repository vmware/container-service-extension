#!/usr/bin/env bash

set -e

cat << EOF > /etc/systemd/system/iptables-ports.service
[Unit]
After=iptables.service
Requires=iptables.service
[Service]
Type=oneshot
ExecStartPre=/usr/sbin/iptables -P INPUT ACCEPT
ExecStartPre=/usr/sbin/iptables -P OUTPUT ACCEPT
ExecStart=/usr/sbin/iptables -P FORWARD ACCEPT
TimeoutSec=0
RemainAfterExit=yes
[Install]
WantedBy=iptables.service
EOF

chmod 766 /etc/systemd/system/iptables-ports.service
systemctl enable iptables-ports.service
systemctl start iptables-ports.service
systemctl enable docker
systemctl start docker

tdnf install -y -q wget gawk kubernetes-1.8.1-3.ph2 kubernetes-kubeadm-1.8.1-3.ph2

docker pull gcr.io/google_containers/kube-controller-manager-amd64:v1.8.1
docker pull gcr.io/google_containers/kube-scheduler-amd64:v1.8.1
docker pull gcr.io/google_containers/kube-apiserver-amd64:v1.8.1
docker pull gcr.io/google_containers/kube-proxy-amd64:v1.8.1
docker pull gcr.io/google_containers/k8s-dns-sidecar-amd64:1.14.4
docker pull gcr.io/google_containers/k8s-dns-kube-dns-amd64:1.14.4
docker pull gcr.io/google_containers/k8s-dns-dnsmasq-nanny-amd64:1.14.4
docker pull gcr.io/google_containers/etcd-amd64:3.0.17
docker pull gcr.io/google_containers/pause-amd64:3.0

docker pull weaveworks/weave-npc:2.0.5
docker pull weaveworks/weave-kube:2.0.5

export kubever=$(kubectl version --client | base64 | tr -d '\n')
wget -O weave.yml "https://cloud.weave.works/k8s/net?k8s-version=$kubever&version=2.0.5"

### common
echo -n > /etc/machine-id
echo 'customization completed'
sync
sync
