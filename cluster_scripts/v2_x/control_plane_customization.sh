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

if [[ x$1 = x"postcustomization" ]];
then
    echo "$(date) This script was called with $1" &>> /var/log/cse/customization/status.log
    echo "$(date) post customization script execution in progress" &>> /var/log/cse/customization/status.log
    tkg_plus_kind="TKG+"
    input_kind="{cluster_kind}"
    kubeadm_config_path=/root/kubeadm-defaults.conf
    ssh_key="{ssh_key}"

    control_plane_end_point="{expose_ip}"

    vmtoolsd --cmd "info-set guestinfo.postcustomization.store.sshkey.status in_progress"
    if [[ ! -z "$ssh_key" ]];
    then
        mkdir -p /root/.ssh
        echo $ssh_key >> /root/.ssh/authorized_keys
        chmod -R go-rwx /root/.ssh
    fi
    vmtoolsd --cmd "info-set guestinfo.postcustomization.store.sshkey.status successful"

    while [[ `systemctl is-active docker` != 'active' ]]; do echo 'waiting for docker'; sleep 5; done

    vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeinit.status in_progress"
    if [[ ! -z "$control_plane_end_point" ]];
    then
        echo "$(date) executing kubeadm init --control-plane-endpoint" &>> /var/log/cse/customization/status.log
        kubeadm init --control-plane-endpoint=$control_plane_end_point:6443 --kubernetes-version=v{k8s_version} --token-ttl=0 > /root/kubeadm-init.out
    else
        echo "$(date) executing kubeadm init" &>> /var/log/cse/customization/status.log
        kubeadm init --kubernetes-version=v{k8s_version} --token-ttl=0 > /root/kubeadm-init.out
    fi
    vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeinit.status successful"

    vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.apply.weave.status in_progress"
    export kubever=$(kubectl version --client | base64 | tr -d '\n')
    mkdir -p /root/.kube
    cp -f /etc/kubernetes/admin.conf /root/.kube/config
    chown $(id -u):$(id -g) /root/.kube/config
    export KUBECONFIG=/etc/kubernetes/admin.conf
    vmtoolsd --cmd "info-set guestinfo.kubeconfig $(cat /etc/kubernetes/admin.conf)"

    WEAVE_VERSIONED_FILE="/root/weave_v$(echo {cni_version} | sed -r 's/\./\-/g').yml"
    echo $WEAVE_VERSIONED_FILE >> /var/log/cse/customization/status.log
    kubectl apply -f $WEAVE_VERSIONED_FILE >> /var/log/cse/customization/status.log 2>> /var/log/cse/customization/error.log
    vmtoolsd --cmd "info-set guestinfo.postcustomization.kubectl.apply.weave.status successful"

    vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.token.generate.status in_progress"
    kubeadm_join_info=$(kubeadm token create --print-join-command 2> /dev/null)
    vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.token.info $kubeadm_join_info"
    vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.token.generate.status successful"
    echo "$(date) post customization script execution completed" &>> /var/log/cse/customization/status.log
fi
