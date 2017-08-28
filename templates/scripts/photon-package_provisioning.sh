#!/bin/sh

# Enable command execution through ESX and VMWare Tools
cat >/etc/pam.d/vmtoolsd << EOF
auth            include         system-auth
account         include         system-account
password        include         system-password
session         include         system-session
EOF

# Install sudo.
/usr/bin/tdnf --assumeyes install sudo

# Install and configure iptables
/usr/bin/tdnf -y install iptables
cat << EOF > /etc/systemd/system/iptables-ports.service
[Unit]
After=iptables.service
Requires=iptables.service
[Service]
Type=oneshot
ExecStartPre=/usr/sbin/iptables -P INPUT ACCEPT
ExecStartPre=/usr/sbin/iptables -P OUTPUT ACCEPT
ExecStart=/usr/sbin/iptables -P FORWARD ACCEPT
TimeoutSec=0
RemainAfterExit=yes
[Install]
WantedBy=iptables.service
EOF
chmod 766 /etc/systemd/system/iptables-ports.service
systemctl enable iptables-ports.service
systemctl start iptables-ports.service

# Install docker
/usr/bin/tdnf -y install docker-1.12.6
systemctl enable docker.service
systemctl start docker.service

# Install Kubernetes
/usr/bin/tdnf -y install kubernetes
/usr/bin/tdnf -y install kubernetes-kubeadm

# Reset machine-id to avoid DHCP issues
echo -n > /etc/machine-id
