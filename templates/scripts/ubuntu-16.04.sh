#!/bin/sh
sudo apt-get update
sudo apt-get install -qy open-vm-tools
sudo apt-get install -qy docker.io
sudo apt-get install -qy apt-transport-https
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
echo "deb http://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update

sudo apt install -y kubelet=1.7.5-00
sudo apt install -y kubeadm=1.7.5-00
sudo apt install -y kubernetes-cni=0.5.1-00

sudo docker pull gcr.io/google_containers/kube-controller-manager-amd64:v1.7.6
sudo docker pull gcr.io/google_containers/kube-scheduler-amd64:v1.7.6
sudo docker pull gcr.io/google_containers/kube-apiserver-amd64:v1.7.6
sudo docker pull gcr.io/google_containers/kube-proxy-amd64:v1.7.6
sudo docker pull gcr.io/google_containers/etcd-amd64:3.0.17
sudo docker pull gcr.io/google_containers/pause-amd64:3.0

sudo docker pull quay.io/coreos/flannel:v0.9.0-amd64
sudo docker pull gcr.io/google_containers/k8s-dns-sidecar-amd64:1.14.4
sudo docker pull gcr.io/google_containers/k8s-dns-kube-dns-amd64:1.14.4
sudo docker pull gcr.io/google_containers/k8s-dns-dnsmasq-nanny-amd64:1.14.4

sudo wget https://raw.githubusercontent.com/coreos/flannel/v0.9.0/Documentation/kube-flannel.yml
