Feature: Container UI landing page

Scenario: Accessing Container UI plugin
  Given User is on Home Page of tenant portal
  When Container UI plugin is not published to the tenant
  And no other UI plugins has been published to the tenant
  Then the User doesn't see the 'More' menu item on the top ribbon

  When Container UI plugin is not published to the tenant
  And atleast one UI plugin is published to the tenant
  And User clicks on 'More' menu item on top ribbon
  Then the drop down menu doesn't displays a 'Kubernetes Container Clusters' entry

  When Container UI plugin is published to the tenant
  And User clicks on 'More' menu item on top ribbon
  Then the drop down menu displays a 'Kubernetes Container Clusters' entry

Scenario: Accessing Container UI plugin landing page
  Given User can access 'Kubernetes Container Clusters' item in the 'More' menu
  When User clicks on it
  Then the Users is navigated to the Container UI plugin's landing page

  When the User is on landing page
  And the User has the role System Administrator
  Then User sees the list of clusters (both TKG and CSE native) owned by them
  And User sees an org column that displays the org to which the cluster belongs

  When the User is on landing page
  And the User doesn't have the role System Administrator
  Then User sees the list of clusters (both TKG and CSE native) owned by them
  And User doesn't see the org column in the table

