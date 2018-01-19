#!/usr/bin/env bash

set -e

echo 'nameserver 8.8.8.8' >> /etc/resolvconf/resolv.conf.d/tail
resolvconf -u
systemctl restart networking.service

growpart /dev/sda 1
resize2fs /dev/sda1

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
apt-get -q dist-upgrade -y
apt-get -q install -y docker-ce=17.12.0~ce-0~ubuntu
apt-get -q install -y kubelet=1.9.1-00 kubeadm=1.9.1-00 kubectl=1.9.1-00 kubernetes-cni=0.6.0-00 --allow-unauthenticated
apt-get -q autoremove -y
systemctl restart docker
while [ `systemctl is-active docker` != 'active' ]; do echo 'waiting for docker'; sleep 5; done

docker pull gcr.io/google_containers/kube-apiserver-amd64:v1.9.1
docker pull gcr.io/google_containers/kube-controller-manager-amd64:v1.9.1
docker pull gcr.io/google_containers/kube-proxy-amd64:v1.9.1
docker pull gcr.io/google_containers/kube-scheduler-amd64:v1.9.1

docker pull gcr.io/google_containers/etcd-amd64:3.1.10
docker pull gcr.io/google_containers/pause-amd64:3.0

docker pull gcr.io/google_containers/k8s-dns-dnsmasq-nanny-amd64:1.14.7
docker pull gcr.io/google_containers/k8s-dns-kube-dns-amd64:1.14.7
docker pull gcr.io/google_containers/k8s-dns-sidecar-amd64:1.14.7

docker pull weaveworks/weave-kube:2.1.3
docker pull weaveworks/weave-npc:2.1.3

export kubever=$(kubectl version --client | base64 | tr -d '\n')
wget -O weave.yml "https://cloud.weave.works/k8s/net?k8s-version=$kubever&version=2.1.3"

curl -L git.io/weave -o /usr/local/bin/weave
chmod a+x /usr/local/bin/weave

mkdir -p /root/go/bin

wget --no-verbose https://storage.googleapis.com/golang/go1.9.2.linux-amd64.tar.gz
tar -xf go1.9.2.linux-amd64.tar.gz

export GOPATH=/root/go
export PATH=$GOPATH/bin:$PATH

echo 'export GOPATH=/root/go' >> /root/.bashrc
echo 'PATH=$GOPATH/bin:$PATH' >> /root/.bashrc

go version
curl https://glide.sh/get | sh

### harbor
curl -L https://github.com/docker/compose/releases/download/1.18.0/docker-compose-`uname -s`-`uname -m` -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
wget --no-verbose https://github.com/vmware/harbor/releases/download/v1.2.2/harbor-offline-installer-v1.2.2.tgz

### common
echo -n > /etc/machine-id
echo 'customization completed'
sync
sync
