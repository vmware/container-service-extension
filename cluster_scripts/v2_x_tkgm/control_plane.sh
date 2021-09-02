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
  exit 0
elif [ "$1" != "postcustomization" ]
then
  echo "$(date) Exiting early since phase is [$1]" &>> /var/log/cse/customization/status.log
  exit 0
fi

echo "$(date) Post Customization script execution in progress" &>> /var/log/cse/customization/status.log

kubeadm_config_path=/root/kubeadm-defaults.conf
vcloud_configmap_path=/root/vcloud-configmap.yaml
vcloud_ccm_path=/root/cloud-director-ccm.yaml
csi_driver_path=/root/csi-driver.yaml
csi_controller_path=/root/csi-controller.yaml
csi_node_path=/root/csi-node.yaml


# This is a simple command but its execution is crucial to kubeadm join. There are a few versions of ubuntu
# where the dbus.service is not started in a timely enough manner to set the hostname correctly. Hence
# this needs to be set by us.
vmtoolsd --cmd "info-set guestinfo.postcustomization.hostname.status in_progress"
hostnamectl set-hostname {vm_host_name}
vmtoolsd --cmd "info-set guestinfo.postcustomization.hostname.status successful"


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


vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeinit.status in_progress"
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

  # create /root/kubeadm-defaults.conf
  echo "---
apiVersion: kubeadm.k8s.io/v1beta2
kind: InitConfiguration
bootstrapTokens:
- groups:
  - system:bootstrappers:kubeadm:default-node-token
  ttl: 0s
  usages:
  - signing
  - authentication
nodeRegistration:
  criSocket: /run/containerd/containerd.sock
  kubeletExtraArgs:
    cloud-provider: external
---
apiVersion: kubeadm.k8s.io/v1beta2
kind: ClusterConfiguration
dns:
  type: CoreDNS
  imageRepository: projects.registry.vmware.com/tkg
  imageTag: $coredns_image_version
etcd:
  local:
    imageRepository: projects.registry.vmware.com/tkg
    imageTag: $etcd_image_version
networking:
  serviceSubnet: {service_cidr}
  podSubnet: {pod_cidr}
imageRepository: projects.registry.vmware.com/tkg
kubernetesVersion: $kubernetes_version
---" > /root/kubeadm-defaults.conf
  kubeadm init --config $kubeadm_config_path > /root/kubeadm-init.out
  export KUBECONFIG=/etc/kubernetes/admin.conf
vmtoolsd --cmd "info-set guestinfo.kubeconfig $(cat /etc/kubernetes/admin.conf | base64 | tr -d '\n')"
vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeinit.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.apply.cni.status in_progress"
  kubectl apply -f https://github.com/vmware-tanzu/antrea/releases/download/v0.11.3/antrea.yml
vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.apply.cni.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.cpi.install.status in_progress"
  # TODO: change to use main branch links
  wget -O $vcloud_configmap_path https://raw.githubusercontent.com/ltimothy7/cloud-provider-for-cloud-director/auth_mount_internal/manifests/vcloud-configmap.yaml
  wget -O $vcloud_ccm_path https://raw.githubusercontent.com/ltimothy7/cloud-provider-for-cloud-director/auth_mount_internal/manifests/cloud-director-ccm.yaml

  kubectl apply -f $vcloud_configmap_path
  kubectl apply -f $vcloud_ccm_path
vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.cpi.install.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.csi.install.status in_progress"
  wget -O $csi_driver_path https://github.com/vmware/cloud-director-named-disk-csi-driver/raw/main/manifests/csi-driver.yaml
  wget -O $csi_controller_path https://github.com/vmware/cloud-director-named-disk-csi-driver/raw/main/manifests/csi-controller.yaml
  wget -O $csi_node_path https://github.com/vmware/cloud-director-named-disk-csi-driver/raw/main/manifests/csi-node.yaml

  kubectl apply -f $csi_driver_path
  kubectl apply -f $csi_controller_path
  kubectl apply -f $csi_node_path
vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.csi.install.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.token.generate.status in_progress"
  kubeadm_join_info=$(kubeadm token create --print-join-command 2> /dev/null)
  vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.token.info $kubeadm_join_info"
vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.token.generate.status successful"


echo "$(date) post customization script execution completed" &>> /var/log/cse/customization/status.log
exit 0
