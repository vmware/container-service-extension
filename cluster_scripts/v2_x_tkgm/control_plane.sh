#!/usr/bin/env bash
set -e

kubeadm_config_path=/root/kubeadm-defaults.conf
vcloud_basic_auth_path=/root/vcloud-basic-auth.yaml
vcloud_configmap_path=/root/vcloud-configmap.yaml
vcloud_ccm_path=/root/cloud-director-ccm.yaml
csi_driver_path=/root/csi-driver.yaml
csi_controller_path=/root/csi-controller.yaml
csi_node_path=/root/csi-node.yaml

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
  if [ "$image" = "coredns" ]; then
    coredns_image_version=new_tag_version
  elif [ "$image" = "etcd" ]; then
    etcd_image_version=new_tag_version
  elif [ "$image" = "kube-proxy" ]; then # selecting other kube-* images would work too
    kubernetes_version=new_tag_version
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

mkdir -p /root/.kube
cp -f /etc/kubernetes/admin.conf /root/.kube/config
chown $(id -u):$(id -g) /root/.kube/config
export kubever=$(kubectl version --client | base64 | tr -d '\n')

kubectl apply -f https://github.com/vmware-tanzu/antrea/releases/download/v0.11.3/antrea.yml
systemctl restart kubelet
while [ `systemctl is-active kubelet` != 'active' ]; do echo 'waiting for kubelet'; sleep 5; done

# Download cpi and csi yaml
#wget -O /root/vcloud-basic-auth.yaml https://raw.githubusercontent.com/vmware/cloud-provider-for-cloud-director/main/manifests/vcloud-basic-auth.yaml
#wget -O /root/vcloud-configmap.yaml https://raw.githubusercontent.com/vmware/cloud-provider-for-cloud-director/main/manifests/vcloud-configmap.yaml
#wget -O /root/cloud-director-ccm.yaml https://raw.githubusercontent.com/vmware/cloud-provider-for-cloud-director/main/manifests/cloud-director-ccm.yaml
# TODO: change to use main branch links
wget -O $vcloud_basic_auth_path https://raw.githubusercontent.com/ltimothy7/cloud-provider-for-cloud-director/auth_mount_internal/manifests/vcloud-basic-auth.yaml
wget -O $vcloud_configmap_path https://raw.githubusercontent.com/ltimothy7/cloud-provider-for-cloud-director/auth_mount_internal/manifests/vcloud-configmap.yaml
wget -O $vcloud_ccm_path https://raw.githubusercontent.com/ltimothy7/cloud-provider-for-cloud-director/auth_mount_internal/manifests/cloud-director-ccm.yaml
wget -O $csi_driver_path https://github.com/vmware/cloud-director-named-disk-csi-driver/raw/main/manifests/csi-driver.yaml
wget -O $csi_controller_path https://github.com/vmware/cloud-director-named-disk-csi-driver/raw/main/manifests/csi-controller.yaml
wget -O $csi_node_path https://github.com/vmware/cloud-director-named-disk-csi-driver/raw/main/manifests/csi-node.yaml

# TODO: look into if not https vcd host
sed -i 's/BASE64_USERNAME/{base64_username}/; s/BASE64_PASSWORD/{base64_password}/' $vcloud_basic_auth_path
sed -i 's/VCD_HOST/"https:\/\/{vcd_host}"/; s/ORG/"{org}"/; s/OVDC/"{ovdc}"/; s/NETWORK/"{ovdc_network}"/; s/VIP_SUBNET_CIDR/"{vip_subnet_cidr_ip}\/{vip_subnet_cidr_suffix}"/; s/CLUSTER_ID/"{cluster_id}"/' $vcloud_configmap_path

kubectl apply -f $vcloud_basic_auth_path
kubectl apply -f $vcloud_configmap_path
kubectl apply -f $vcloud_ccm_path
kubectl apply -f $csi_driver_path
kubectl apply -f $csi_controller_path
kubectl apply -f $csi_node_path
