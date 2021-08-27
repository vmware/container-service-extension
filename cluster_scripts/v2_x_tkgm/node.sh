#!/usr/bin/env bash

catch() {{
   vmtoolsd --cmd "info-set guestinfo.post_customization_script_execution_status $?"
   error_message="$(date) $(caller): $BASH_COMMAND"
   echo "$error_message" &>> /var/log/cse/customization/error.log
   vmtoolsd --cmd "info-set guestinfo.post_customization_script_execution_failure_reason $error_message"
}}

mkdir -p /var/log/cse/customization

trap 'catch $? $LINENO' ERR

set -e

echo "$(date) This script was called with $1" &>> /var/log/cse/customization/status.log

if [ "$1" == "precustomization" ]
then
  echo "$(date) Exiting early since phase is [$1]" &>> /var/log/cse/customization/status.log
  vmtoolsd --cmd "info-set guestinfo.precustomization.script.status successful"
  exit 0
elif [ "$1" != "postcustomization" ]
then
  echo "$(date) Exiting early since phase is [$1]" &>> /var/log/cse/customization/status.log
  exit 0
fi

echo "$(date) Post Customization script execution in progress" &>> /var/log/cse/customization/status.log

# This is a simple command but its execution is crucial to kubeadm join. There are a few versions of ubuntu
# where the dbus.service is not started in a timely enough manner to set the hostname correctly. Hence
# this needs to be set by us.
vmtoolsd --cmd "info-set guestinfo.postcustomization.hostname.status in_progress"
hostnamectl set-hostname {vm_host_name}
vmtoolsd --cmd "info-set guestinfo.postcustomization.hostname.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.networkconfiguration.status in_progress"
  echo 'net.ipv6.conf.all.disable_ipv6 = 1' >> /etc/sysctl.conf
  echo 'net.ipv6.conf.default.disable_ipv6 = 1' >> /etc/sysctl.conf
  echo 'net.ipv6.conf.lo.disable_ipv6 = 1' >> /etc/sysctl.conf
  sudo sysctl -p

  # also remove ipv6 localhost entry from /etc/hosts
  sed -i 's/::1/127.0.0.1/g' /etc/hosts || true
vmtoolsd --cmd "info-set guestinfo.postcustomization.networkconfiguration.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.store.sshkey.status in_progress"
  ssh_key="{ssh_key}"
  if [[ ! -z "$ssh_key" ]];
  then
    mkdir -p /root/.ssh
    echo $ssh_key >> /root/.ssh/authorized_keys
    chmod -R go-rwx /root/.ssh
  fi
vmtoolsd --cmd "info-set guestinfo.postcustomization.store.sshkey.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.nameserverconfig.resolvconf.status in_progress"
  echo 'nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 10.16.188.210
nameserver 10.118.254.1' > /etc/resolv.conf
vmtoolsd --cmd "info-set guestinfo.postcustomization.nameserverconfig.resolvconf.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.node.join.status in_progress"
  kubeadm_config_path=/root/kubeadm-defaults-join.conf

  # tag images
  coredns_image_version=""
  etcd_image_version=""
  kubernetes_version=""
  for image in "coredns" "etcd" "kube-proxy" "kube-apiserver" "kube-controller-manager" "kube-scheduler"
  do
    image_ref=$(ctr -n=k8s.io image list | cut -d" " -f1 | grep $image)
    ref_path=$(echo $image_ref | sed 's/:.*//')
    new_tag_version=$(echo $image_ref | sed 's/.*://' | sed 's/_/-/')
    ctr -n=k8s.io image tag $image_ref $ref_path:$new_tag_version

    # save image tags for later
    if [[ "$image" = "coredns" ]]; then
      coredns_image_version=$new_tag_version
    elif [[ "$image" = "etcd" ]]; then
      etcd_image_version=$new_tag_version
    elif [[ "$image" = "kube-proxy" ]]; then # selecting other kube-* images would work too
      kubernetes_version=$new_tag_version
    fi
  done

  echo "---
apiVersion: kubeadm.k8s.io/v1beta2
kind: JoinConfiguration
caCertPath: /etc/kubernetes/pki/ca.crt
discovery:
  bootstrapToken:
    apiServerEndpoint: {ip_port}
    token: {token}
    unsafeSkipCAVerification: false
    caCertHashes: [{discovery_token_ca_cert_hash}]
  timeout: 5m0s
nodeRegistration:
  criSocket: /run/containerd/containerd.sock
  kubeletExtraArgs:
    cloud-provider: external
---" > /root/kubeadm-defaults-join.conf

  kubeadm join --config $kubeadm_config_path
vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.node.join.status successful"

echo "$(date) post customization script execution completed" &>> /var/log/cse/customization/status.log

exit 0

