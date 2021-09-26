#!/usr/bin/env bash

catch() {{
  retval=$?
   error_message="$(date) $(caller): $BASH_COMMAND"
   echo "$error_message" &>> /var/log/cse/customization/error.log
   vmtoolsd --cmd "info-set guestinfo.post_customization_script_execution_failure_reason $error_message"
   vmtoolsd --cmd "info-set guestinfo.post_customization_script_execution_status $retval"
}}

mkdir -p /var/log/cse/customization

trap 'catch $? $LINENO' ERR

set -ex

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

vcloud_basic_auth_path=/root/vcloud-basic-auth.yaml
vcloud_configmap_path=/root/vcloud-configmap.yaml
vcloud_ccm_path=/root/cloud-director-ccm.yaml

vcloud_csi_configmap_path=/root/vcloud-csi-configmap.yaml
csi_driver_path=/root/csi-driver.yaml
csi_controller_path=/root/csi-controller.yaml
csi_node_path=/root/csi-node.yaml


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
  cat > $kubeadm_config_path << END
---
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
controlPlaneEndpoint: "{control_plane_endpoint}"
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
---
END

  kubeadm init --config $kubeadm_config_path > /root/kubeadm-init.out
  export KUBECONFIG=/etc/kubernetes/admin.conf
vmtoolsd --cmd "info-set guestinfo.kubeconfig $(cat /etc/kubernetes/admin.conf | base64 | tr -d '\n')"
vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeinit.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.apply.cni.status in_progress"
  antrea_path=/root/antrea-{antrea_cni_version}.yaml
  wget -O $antrea_path https://github.com/vmware-tanzu/antrea/releases/download/{antrea_cni_version}/antrea.yml
  # This does not need to be done from v0.12.0 onwards inclusive
  sed -i 's/antrea\/antrea-ubuntu:{antrea_cni_version}/projects.registry.vmware.com\/antrea\/antrea-ubuntu:{antrea_cni_version}/g' $antrea_path
  kubectl apply -f $antrea_path
vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.apply.cni.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.cpi.install.status in_progress"
  wget -O $vcloud_basic_auth_path https://raw.githubusercontent.com/vmware/cloud-provider-for-cloud-director/0.1.0-beta/manifests/vcloud-basic-auth.yaml
  kubectl apply -f $vcloud_basic_auth_path

  wget -O $vcloud_configmap_path https://raw.githubusercontent.com/arunmk/cloud-provider-for-cloud-director/main/manifests/vcloud-configmap.yaml
  sed -i 's/VCD_HOST/"{vcd_host}"/' $vcloud_configmap_path
  sed -i 's/ORG/"{org}"/' $vcloud_configmap_path
  sed -i 's/OVDC/"{vdc}"/' $vcloud_configmap_path
  sed -i 's/NETWORK/"{network_name}"/' $vcloud_configmap_path
  sed -i 's/VIP_SUBNET_CIDR/"{vip_subnet_cidr}"/' $vcloud_configmap_path
  sed -i 's/VAPP/{cluster_name}/' $vcloud_configmap_path
  sed -i 's/CLUSTER_ID/{cluster_id}/' $vcloud_configmap_path
  kubectl apply -f $vcloud_configmap_path

  wget -O $vcloud_ccm_path https://raw.githubusercontent.com/vmware/cloud-provider-for-cloud-director/main/manifests/cloud-director-ccm.yaml
  kubectl apply -f $vcloud_ccm_path
vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.cpi.install.status successful"


vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.csi.install.status in_progress"
  wget -O $vcloud_csi_configmap_path https://raw.githubusercontent.com/arunmk/cloud-director-named-disk-csi-driver/main/manifests/vcloud-csi-config.yaml
  sed -i 's/VCD_HOST/"{vcd_host}"/' $vcloud_csi_configmap_path
  sed -i 's/ORG/"{org}"/' $vcloud_csi_configmap_path
  sed -i 's/OVDC/"{vdc}"/' $vcloud_csi_configmap_path
  sed -i 's/VAPP/{cluster_name}/' $vcloud_csi_configmap_path
  sed -i 's/CLUSTER_ID/"{cluster_id}"/' $vcloud_csi_configmap_path
  kubectl apply -f $vcloud_csi_configmap_path

  wget -O $csi_driver_path https://raw.githubusercontent.com/vmware/cloud-director-named-disk-csi-driver/main/manifests/csi-driver.yaml
  wget -O $csi_controller_path https://raw.githubusercontent.com/vmware/cloud-director-named-disk-csi-driver/main/manifests/csi-controller.yaml
  wget -O $csi_node_path https://raw.githubusercontent.com/vmware/cloud-director-named-disk-csi-driver/main/manifests/csi-node.yaml
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
