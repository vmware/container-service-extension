Feature: Interact with TKG clusters

Rules:
  - CSE UI plugin is published to tenant
  - User is on CSE UI plugin's landing page
  - TKG is enabled in vCenter
  - At least one of the oVDC in the org is configured to host TKG clusters

Scenario: Create TKG cluster
  When User clicks on 'Add' button on CSE UI plugin landing page
  Then User sees the 'General' section of the cluster create wizard
  And User fills out the name and description of the cluster 

  When User clicks on Next button
  Then User sees the choice of Kubernetes run-times viz. vSphere with Tanzu (aka TKG) and Native (as radio buttons)

  When User chooses vSphere with Tanzu radio button
  And User clicks on Next
  Then User sees all the oVDCs as cards, that are enabled for TKG cluster deployment
  And User chooses one of them by clicking on the radio button in one of the cards

  When User clicks on Next button
  Then User sees the 'Kubernetes Policy' section of the wizard
  And User sees a list of Kubernetes policies that have been published to the selected oVDC
  And User selects one of them, by clicking on the radio of the entry

  When User clicks on Next button
  Then User sees the 'Sizing' section of the wizard
  And User sees the current number of Control Plane nodes as 1 (non editable field)
  And User enters the desired number of worker nodes (default is set to 3)

  When User enters a negative value for desired number of worker nodes
  Then User sees an appropriate error message

  When User continues to fill the section of the wizard
  And User sees list of Sizing policies published to the oVDC
  And User chooses a policy for the control plane nodes
  And User chooses a policy for the worker nodes

  When User clicks on Next button
  Then User sees the 'Network' section of the wizard
  And User chooses a network from a list of networks available to the selected oVDC, by clicking on radio button

  When User clicks on Next button
  Then User sees the 'Review' section of the wizard
  And User can review the details of the cluster to be created

  When User clicks on 'Create' button
  Then User is taken back to the landing page
  And they see the cluster to be created listed on the page in "CREATE : IN PROGRESS" state

  When Cluster creation is complete
  Then the cluster entry on landing page displays it's state as "READY"


Scenario: Fetch TKG cluster's kubectl config
  Given cluster 'mycluster' has been previously created by User
  When User selects the radio button in front of the entry of 'mycluster'
  Then the 'Download KubeConfig' button turns from grayed out to enabled

  When User clicks on 'Download KubeConfig' button
  Then cluster 'mycluster''s kubectl config is fetched from VCD and downloaded as yaml file by the browser


Scenario: Delete a TKG cluster
  Given cluster 'mycluster' has been previously created by User
  When User selects the radio button in front of the entry of 'mycluster'
  Then the 'Delete' button turns from grayed out to enabled

  When User clicks on 'Delete' button
  Then a confirmation dialog pops up

  When User selects 'Yes' on the confirmation dialog
  Then a task tracking the deletion of the cluster shows up in the tasks tab

  When the status of the task tracking the deletion of cluster changes to completed
  Then the cluster 'mycluster' has been successfully deleted


Scenario: Resize a TKG cluster
  Given cluster 'mycluster' has been previously created by User
  When User selects the radio button in front of the entry of 'mycluster'
  Then the 'Re-Size' button turns from grayed out to enabled

  When User clicks on 'Re-Size' button
  Then the 'Re-Size cluster' dialog pops up

  When User enters the new number of worker nodes
  And the input is bigger than current number of worker nodes in the cluster
  Then a message is displayed in the dialog, which lets the User know how many nodes would be added

  When User enters the new number of worker nodes
  And the input is smaller than current number of worker nodes in the cluster
  Then a message is displayed in the dialog, which lets the User know how many nodes would be deleted

  When User enters the new number of worker nodes
  And the input is less than 0 or invalid
  Then an appropriate error message is displayed in the dialog

  When clicks on 'Re-Size' button the dialog
  Then a task tracking the resize operation on the cluster shows up in the tasks tab

  When the task tracking the resize operation shows as completed
  Then the cluster 'mycluster' has been successfully resized to the desired number of worker nodes