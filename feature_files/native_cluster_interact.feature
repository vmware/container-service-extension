Feature: Interact with CSE native clusters

Rules:
  - CSE UI plugin is published to tenant
  - User is on CSE UI plugin's landing page

Scenario: Create CSE native cluster
  When User clicks on 'New' button on CSE UI plugin landing page
  Then User sees the 'General' section of the cluster create wizard
  And User fills out the name and description of the cluster 

  When User clicks on Next button in General section
  Then User sees the 'Kubernetes Runtime' section

  When User sees the 'Kubernetes Runtime' section
  And there are no org VDC that is enabled for native K8s clusters
  And there are no org VDC that is enabled for TKG clusters
  Then User doesn't see any cards on the dialog
  And User sees an error message stating that there are no org VDC that can host K8s clusters.

  When User sees the 'Kubernetes Runtime' section
  And atleast one org VDC is enabled for native K8s clusters
  And there is a card in the dialog, viz. 'Native' as an option for K8s runtime

  When User chooses Native radio button
  Then User is presented with a list of K8s template that are available to deploy a native cluster
  And User is presented a text box to enter the SSH public key to access cluster vms later

  When User chooses a template
  And User enters SSH key details
  And User clicks on Next
  Then User sees all the oVDCs as cards, that are enabled for Native cluster deployment
  And User chooses one of them by clicking on the radio button in one of the cards

  When User clicks on Next button
  Then User sees the 'Compute' section of the wizard
  And User specifies the number of worker nodes (default is set to 2)

  When User specifies negative or non integer number of worker nodes
  Then User sees relevant error next to the field

  When User continues to fill the section of the wizard
  And User sees number of control plane nodes set to 1 and this field is not editable
  And User selects Sizing policy from a drop down list containing the policies available to the oVDC selected in last step
  And User specifies number of CPU cores
  And User specifies amount of memory

  When User clicks on Next button
  Then User sees the 'Storage' section of the wizard
  And User chooses a storage profile from the drop down list
  And User can toggle the 'Enable NFS' radio button (defaulted to off state)

  When User clicks on Next button
  Then User sees the 'Network' section of the wizard
  And User chooses a network from a list of networks available to the selected oVDC, by clicking on radio button

  When User clicks on Next button
  Then User sees the 'Review' section of the wizard
  And User can review the details of the cluster to be created
  And User can add a NFS node to the cluster by turning on the 'Enable NFS' toggle button

  When User clicks on 'Create' button
  And User doesn't have DEF rights assigned to their role
  Then User sees a modal dialog informing the User of the error
  And User is taken back to the landing page on dismissing the modal dialog
  And User sees the cluster create task in failed state with the appropriate error message

  When User clicks on 'Create' button
  And User has DEF rights assigned to their role
  Then User sees a modal dialog informing the User that CSE server has accepted their request to create a cluster
  And User is taken back to the landing page on dismissing the modal dialog.
  And they see the cluster to be created listed on the page in "CREATE : IN PROGRESS" state

  When Cluster creation is complete
  Then the cluster entry on landing page displays it's state as "READY"


Scenario: Fetch CSE native cluster's kubectl config
  Given cluster 'mycluster' has been previously created by User
  When User selects the radio button in front of the entry of 'mycluster'
  Then the 'Download Kube Config' button turns from grayed out to enabled

  When User clicks on 'Download Kube Config' button
  And User doesn't have the required DEF right in their role
  Then no error messages are shown
  And the button appears to perform no action

  When User clicks on 'Download Kube Config' button
  And User has the required DEF right in their role
  Then cluster 'mycluster''s kubectl config is fetched from CSE server and downloaded as yaml file by the browser


Scenario: Delete a CSE native cluster
  Given cluster 'mycluster' has been previously created by User
  When User selects the radio button in front of the entry of 'mycluster'
  Then the 'Delete' button turns from grayed out to enabled

  When User clicks on 'Delete' button
  Then a confirmation dialog pops up

  When User selects 'Yes' on the confirmation dialog
  And User doesn't have required DEF rights assigned to their role
  Then User sees a modal dialog informing the User of the error
  And User is taken back to the landing page on dismissing the modal dialog
  And User sees the cluster delete task in failed state with the appropriate error message

  When User selects 'Yes' on the confirmation dialog
  And User has required DEF rights assigned to their role
  Then User sees a modal dialog informing the User that CSE server has accepted their request to delete the cluster
  And User is taken back to the landing page on dismissing the modal dialog.
  And a task tracking the deletion of the cluster shows up in the tasks tab

  When the status of the task tracking the deletion of cluster changes to completed
  Then the cluster 'mycluster' has been successfully deleted


Scenario: Resize a CSE native cluster
  Given cluster 'mycluster' has been previously created by User
  When User selects the radio button in front of the entry of 'mycluster'
  Then the 'Resize' button turns from grayed out to enabled

  When User clicks on 'Resize' button
  Then the 'Resize cluster' dialog pops up

  When User enters the new number of worker nodes
  And the input is bigger than current number of worker nodes in the cluster
  Then a message is displayed in the dialog, which lets the User know the number of nodes the cluster will be scaled up to

  When User enters the new number of worker nodes
  And the input is smaller than current number of worker nodes in the cluster
  Then a message is displayed in the dialog, which lets the User know the number of nodes the cluster will be scaled down to

  When User enters the new number of worker nodes
  And the input is less than 0 or invalid
  Then an appropriate error message is displayed in the dialog

  When User clicks on 'Resize' button the dialog
  And User doesn't have the required DEF rights assigned to their role
  Then User sees a modal dialog informing the User of the error
  And User is taken back to the landing page on dismissing the modal dialog
  And User sees the cluster resize task in failed state with the appropriate error message

  When User clicks on 'Resize' button the dialog
  And User has the required DEF rights assigned to their role
  Then User sees a modal dialog informing the User of the error
  And User is taken back to the landing page on dismissing the modal dialog
  And User sees a task tracking the resize operation on the cluster show up in the tasks tab

  When the task tracking the resize operation shows as completed
  Then the cluster 'mycluster' has been successfully resized to the desired number of worker nodes