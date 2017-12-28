#!/usr/bin/env bash

while [ `systemctl is-active docker` != 'active' ]; do systemctl is-active docker; sleep 5; done
kubeadm join --token {token} {ip}:6443
