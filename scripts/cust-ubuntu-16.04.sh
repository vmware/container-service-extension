#!/usr/bin/env bash
echo 'nameserver 8.8.8.8' >> /etc/resolvconf/resolv.conf.d/tail
resolvconf -u
systemctl restart networking.service

growpart /dev/sda 1
resize2fs /dev/sda1

apt-get update
apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
cat <<EOF > /etc/apt/sources.list.d/kubernetes.list
deb http://apt.kubernetes.io/ kubernetes-xenial main
EOF
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
apt-get update
apt-get install -y docker-ce=17.09.0~ce-0~ubuntu
apt-get install -y kubelet=1.8.2-00 kubeadm=1.8.2-00 kubectl=1.8.2-00 kubernetes-cni=0.5.1-00 --allow-unauthenticated
apt-get autoremove -y
systemctl restart docker
docker pull gcr.io/google_containers/kube-controller-manager-amd64:v1.8.2
docker pull gcr.io/google_containers/kube-scheduler-amd64:v1.8.2
docker pull gcr.io/google_containers/kube-apiserver-amd64:v1.8.2
docker pull gcr.io/google_containers/kube-proxy-amd64:v1.8.2
docker pull gcr.io/google_containers/etcd-amd64:3.0.17
docker pull gcr.io/google_containers/pause-amd64:3.0
docker pull gcr.io/google_containers/k8s-dns-sidecar-amd64:1.14.5
docker pull gcr.io/google_containers/k8s-dns-kube-dns-amd64:1.14.5
docker pull gcr.io/google_containers/k8s-dns-dnsmasq-nanny-amd64:1.14.5
docker pull weaveworks/weave-npc:2.0.5
docker pull weaveworks/weave-kube:2.0.5
docker pull weaveworks/weaveexec:2.0.5

export kubever=$(kubectl version --client | base64 | tr -d '\n')
wget -O weave.yml "https://cloud.weave.works/k8s/net?k8s-version=$kubever&version=2.0.5"

curl -L git.io/weave -o /usr/local/bin/weave
chmod a+x /usr/local/bin/weave

mkdir -p /root/go/bin
mkdir -p /root/go/src/github.com/vmware/container-service-extension/pv

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
