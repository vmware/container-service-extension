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
    echo "$(date) post customization script execution in progress" &>> /var/log/cse/customization/status.log
    ssh_key="{ssh_key}"

    vmtoolsd --cmd "info-set guestinfo.postcustomization.store.sshkey.status in_progress"
    if [[ ! -z "$ssh_key" ]];
    then
        mkdir -p /root/.ssh
        echo $ssh_key >> /root/.ssh/authorized_keys
        chmod -R go-rwx /root/.ssh
    fi
    vmtoolsd --cmd "info-set guestinfo.postcustomization.store.sshkey.status successful"

    while [[ `systemctl is-active docker` != 'active' ]]; do echo 'waiting for docker'; sleep 5; done

    vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.node.join.status in_progress"
    echo "$(date) executing {kubeadm_join_cmd} on the node" &>> /var/log/cse/customization/status.log
    {kubeadm_join_cmd} >> /var/log/cse/customization/status.log 2>> /var/log/cse/customization/error.log
    vmtoolsd --cmd "info-set guestinfo.postcustomization.kubeadm.node.join.status successful"
    echo "$(date) post customization script execution completed" &>> /var/log/cse/customization/status.log
fi
