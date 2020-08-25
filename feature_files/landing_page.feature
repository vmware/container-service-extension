Feature: CSE landing page

Scenario: Accessing CSE UI plugin
  Given User is on Home Page of tenant portal
  When CSE UI plugin is not published to the tenant
  And no other UI plugins has been published to the tenant
  Then the User doesn't see the 'More' menu item on the top ribbon

  When CSE UI plugin is not published to the tenant
  And atleast one UI plugin is published to the tenant
  And User clicks on 'More' menu item on top ribbon
  Then the drop down menu doesn't displays a 'Kubernetes Container Clusters' entry

  When CSE UI plugin is published to the tenant
  And User clicks on 'More' menu item on top ribbon
  Then the drop down menu displays a 'Kubernetes Container Clusters' entry

Scenario: Accessing CSE UI plugin landing page
  Given User can access 'Kubernetes Container Clusters' item in the 'More' menu
  When User clicks on it
  Then the Users is navigated to the CSE UI plugin's landing page
  And User sees the list of clusters (both TKG and CSE native) owned by them



