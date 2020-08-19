Feature: CSE landing page

Scenario: Accessing CSE UI plugin
  Given User is on Home Page of tenant portal
  When User clicks on 'Applications' menu on top ribbon
  And CSE UI plugin is published to the tenant
  Then the second level ribbon displays 'Kubernetes Clusters' entry

  When User clicks on 'Applications' menu on top ribbon
  And CSE UI plugin is not published to the tenant
  Then the second level ribbon doesn't display 'Kubernetes Clusters' entry

Scenario: Accessing CSE UI plugin landing page
  Given User can access 'Kubernetes Clusters' item in the 'Applications' menu
  When User clicks on it
  Then the Users sees the list of clusters (both TKG and CSE native) owned by them



