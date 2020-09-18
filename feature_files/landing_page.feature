Feature: Container UI plugin landing page

Scenario: Accessing Container UI plugin
  Given User is on Home Page of tenant portal
  When Container UI plugin is not published to the tenant
  And no other UI plugin has been published to the tenant
  Then the User doesn't see the 'More' menu item on the top ribbon

  When Container UI plugin is not published to the tenant
  And at least one UI plugin is published to the tenant
  And User clicks on 'More' menu item on top ribbon
  Then the drop down menu doesn't display a 'Kubernetes Container Clusters' entry

  When Container UI plugin is published to the tenant
  And User clicks on 'More' menu item on top ribbon
  Then the drop down menu displays a 'Kubernetes Container Clusters' entry

Scenario: Accessing Container UI plugin landing page
  Given User can access 'Kubernetes Container Clusters' item in the 'More' menu
  When User clicks on it
  Then the Users is navigated to the Container UI plugin's landing page

  When the User is on landing page
  And the User has the role System Administrator
  Then User sees the collective list of clusters (both TKG and CSE native) owned by all users
  And User sees an 'Organization' column that displays the organization to which the cluster belongs

  When the User is on landing page
  And the User doesn't have the role System Administrator
  Then User sees the list of clusters (both TKG and CSE native) owned by them
  And User doesn't see the 'Organization' column in the table

  When the User is on landing page
  Then the Users sees the columns : Name, Status, Kubernetes Provider, Kubernetes Version, Virtual Data Center, Owner