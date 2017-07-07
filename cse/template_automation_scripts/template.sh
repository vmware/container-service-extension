#!/bin/bash

packer build kub.json
/Applications/VMware\ OVF\ Tool/ovftool $HOME/workspace/kub/packer/output-Photon-Master/master.vmx $HOME/workspace/kub/packer/master.ova

/Applications/VMware\ OVF\ Tool/ovftool $HOME/workspace/kub/packer/output-Photon-Minion/minion.vmx $HOME/workspace/kub/packer/minion.ova

/Applications/VMware\ OVF\ Tool/ovftool --name=master --sourceType=OVA --noSSLVerify --acceptAllEulas --powerOn --diskMode=thin --X:waitForIp --X:enableHiddenProperties  --allowAllExtraConfig --datastore="sharedVmfs-0" --network="VM Network" --ipAllocationPolicy=dhcpPolicy $HOME/workspace/kub/packer/master.ova "vcloud://"$1":"$2"@"$3"?org="$4"&vappTemplate=test&catalog="$5"&vdc="$6

/Applications/VMware\ OVF\ Tool/ovftool --name=minion --sourceType=OVA --noSSLVerify --acceptAllEulas --powerOn --diskMode=thin --X:waitForIp --X:enableHiddenProperties  --allowAllExtraConfig --datastore="sharedVmfs-0" --network="VM Network" --ipAllocationPolicy=dhcpPolicy $HOME/workspace/kub/packer/minion.ova "vcloud://"$1":"$2"@"$3"?org="$4"&vappTemplate=test&catalog="$5"&vdc="$6