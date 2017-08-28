#!/bin/sh
sudo apt-get update
sudo apt-get install -qy open-vm-tools
sudo apt-get install -qy docker.io
sudo apt-get install -qy apt-transport-https
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
echo "deb http://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubernetes-cni
