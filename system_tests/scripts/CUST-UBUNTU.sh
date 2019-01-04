#!/usr/bin/env bash

set -e

echo 'net.ipv6.conf.all.disable_ipv6 = 1' >> /etc/sysctl.conf
echo 'net.ipv6.conf.default.disable_ipv6 = 1' >> /etc/sysctl.conf
echo 'net.ipv6.conf.lo.disable_ipv6 = 1' >> /etc/sysctl.conf
echo 'nameserver 8.8.8.8' >> /etc/resolvconf/resolv.conf.d/tail
resolvconf -u
systemctl restart networking.service
while [ `systemctl is-active networking` != 'active' ]; do echo 'waiting for network'; sleep 5; done

growpart /dev/sda 1 || :
resize2fs /dev/sda1 || :

echo 'installing kubernetes'
export DEBIAN_FRONTEND=noninteractive
apt-get -q update
apt-get -q install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
cat <<EOF > /etc/apt/sources.list.d/kubernetes.list
deb http://apt.kubernetes.io/ kubernetes-xenial main
EOF
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
apt-get -q update
apt-get -q install -y docker-ce=18.03.0~ce-0~ubuntu
apt-get -q install -y kubelet=1.10.11-00 kubeadm=1.10.11-00 kubectl=1.10.11-00 kubernetes-cni=0.6.0-00 --allow-unauthenticated
apt-get -q autoremove -y
systemctl restart docker
while [ `systemctl is-active docker` != 'active' ]; do echo 'waiting for docker'; sleep 5; done

echo 'downloading container images'
docker pull k8s.gcr.io/kube-apiserver-amd64:v1.10.11
docker pull k8s.gcr.io/kube-controller-manager-amd64:v1.10.11
docker pull k8s.gcr.io/kube-proxy-amd64:v1.10.11
docker pull k8s.gcr.io/kube-scheduler-amd64:v1.10.11

docker pull k8s.gcr.io/etcd-amd64:3.1.12
docker pull k8s.gcr.io/pause-amd64:3.1

docker pull k8s.gcr.io/k8s-dns-dnsmasq-nanny-amd64:1.14.8
docker pull k8s.gcr.io/k8s-dns-kube-dns-amd64:1.14.8
docker pull k8s.gcr.io/k8s-dns-sidecar-amd64:1.14.8

docker pull weaveworks/weave-kube:2.3.0
docker pull weaveworks/weave-npc:2.3.0

export kubever=$(kubectl version --client | base64 | tr -d '\n')
wget --no-verbose -O weave.yml "https://cloud.weave.works/k8s/net?k8s-version=$kubever&v=2.3.0"

curl -L git.io/weave -o /usr/local/bin/weave
chmod a+x /usr/local/bin/weave

echo 'installing required software for NFS'
apt-get -q install -y nfs-common nfs-kernel-server
systemctl stop nfs-kernel-server.service
systemctl disable nfs-kernel-server.service


### common
echo 'upgrading the system'
# apt-mark hold open-vm-tools

### this line results in a grub update that presents a selection menu,
### which hangs and results in failed customization. 
### This is a temporary change that will be fixed soon
# apt-get -q dist-upgrade -y
# apt-get -q autoremove -y

echo -n > /etc/machine-id
sync
sync
echo 'customization completed'
