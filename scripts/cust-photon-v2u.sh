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

chmod 0644 /etc/systemd/system/iptables-ports.service
systemctl enable iptables-ports.service
systemctl start iptables-ports.service

#Update Docker (17.06.xx is latest in PhotonOS repos) - do NOT use tdnf for Docker updates after this:
echo 'Updating Docker'
tdnf install -yq wget tar
cp /usr/lib/systemd/system/docker.service /tmp/
tdnf erase -y docker
mv /tmp/docker.service /usr/lib/systemd/system/
wget -qO- https://download.docker.com/linux/static/stable/x86_64/docker-18.06.1-ce.tgz | tar xvz -C /usr/bin/ --strip-components 1
groupadd -r docker
systemctl enable docker
systemctl start docker
while [ `systemctl is-active docker` != 'active' ]; do echo 'waiting for docker'; sleep 5; done

echo 'installing kuberentes'
tdnf install -yq kubernetes-1.11.6-1.ph2 kubernetes-kubeadm-1.11.6-1.ph2

echo 'downloading container images'
docker pull gcr.io/google_containers/kube-controller-manager-amd64:v1.11.6
docker pull gcr.io/google_containers/kube-scheduler-amd64:v1.11.6
docker pull gcr.io/google_containers/kube-apiserver-amd64:v1.11.6
docker pull gcr.io/google_containers/kube-proxy-amd64:v1.11.6
docker pull gcr.io/google_containers/k8s-dns-sidecar-amd64:1.15.0
docker pull gcr.io/google_containers/k8s-dns-kube-dns-amd64:1.15.0
docker pull gcr.io/google_containers/k8s-dns-dnsmasq-nanny-amd64:1.15.0
docker pull gcr.io/google_containers/etcd-amd64:3.1.17
docker pull gcr.io/google_containers/pause-amd64:3.1
#
docker pull weaveworks/weave-npc:2.5.0
docker pull weaveworks/weave-kube:2.5.0

export kubever=$(kubectl version --client | base64 | tr -d '\n')
wget --no-verbose -O weave.yml "https://cloud.weave.works/k8s/net?k8s-version=$kubever&v=2.5.0"


#Installing NFS
echo 'installing required software for NFS'
tdnf -y install nfs-utils
systemctl stop nfs-server.service
systemctl disable nfs-server.service

### common
# echo 'upgrading the system'
# tdnf -yq distro-sync --refresh
echo 'Notice: system not upgraded to the latest version'

echo -n > /etc/machine-id
sync
sync
echo 'customization completed'
