---
layout: default
title: CSE UI Plugin for vCD
---
# CSE UI plugin for vCD

## Overview
Along with CSE 2.6.0, we are releasing CSE UI plugin for vCD. Using this plugin,
CSE users would be able to interact with CSE Kubernetes clusters directly from
vCD UI.

## Getting the plugin
The plugin binary can be downloaded from [here](https://github.com/vmware/container-service-extension/raw/master/cse_ui/1.0.0.0b1/container-ui-plugin.zip).

## Setting up the plugin
### Registering and publishing the plugin
**Method 1:** Via `manage_plugin` script.

Extract the CSE UI plugin zip viz. `container-ui-plugin.zip`.
Download the plugin registration script from [here](https://raw.githubusercontent.com/vmware/container-service-extension/master/cse_ui/1.0.0.0b1/manage_plugin.py).
Save the script content as `manage_plugin.py`.

Fill up the following json template and save it as `manage_plugin.json`, keep
it adjacent to the plugin binary and the registration script.
```json
{
  "username": "[Fill in username of a vCD System Administrator account]",
  "org": "System",
  "password": "[Fill in password of the System Administrator account]",
  "vcdUrlBase": "[Fill in the vCD public endpoint e.g. https://vcd.mydomain.com]"
}
```

To register the plugin, run
```sh
python manage_plugin.py register
```
To unregister the plugin, first you need to figure out the ID of the plugin. List
all installed plugins, and get ID of the CSE UI Plugin, by running
```sh
python manage_plugin.py list
```
Run the following command to remove the plugin from vCD.
```sh
python manage_plugin.py unregister [ID]
```

**Method 2:** Via vCD UI portal

To register the plugin, upload `container-ui-plugin.zip` to vCD through `Customize Portal`
option in the navigation menu of vCD Service Provider view. Then follow the
standard steps of publishing an UI plugin. After registration, refresh the page.
There should be a `Kubernetes Container Clusters` option in the navigation menu.

To unregister the plugin, select the plugin in `Customize Portal` and click on
`DELETE` button.

### Access Control
Tenant users themselves do not have the authority to register/unregister the
plugin. They can only use the plugin once access to it has been granted by
Service Provider. Service Provider has the authority to enable or disable and
manage access control to the UI Plugin.

#### Enable/Disable plugin
From `Customize Portal`, choose the plugin to be enabled/disabled, then click on
`ENABLE` or `DISABLE` button. Once the plugin has been disabled and the page
has been refreshed, the plugin should be inaccessible from both provider and
tenant view.

#### Access control for tenants
From `Customize Portal`, choose the plugin, click on `PUBLISH` button. Then in
the wizard, customize the scope to publish. To remove plugin access from
certain tenants, just un-select them from the scope and then publish.

## Functionality
### Landing Page
After selecting `Kubernetes Container Clusters` option in the navigation menu,
users can access the landing page. Landing page displays a list of Kubernetes
container clusters created from Container Service Extension (CSE) and their
basic information.

**Provider View**

For Service Provider, it shows all the clusters from all organizations from
current vCloud Director.

**Tenant View**

For Tenants, it shows clusters created in current organization.
* Organization Administrator - can view all clusters in the current organization.
* Catalog author, vApp user and console access only roles - can view clusters
  created by catalog authors.
* vApp author - can view only self owned clusters.

All columns can be sorted and filtered. Upon clicking on the cluster name, users
can view the details page of the corresponding cluster.

### Details Page
Upon clicking on a container cluster, it takes you to it's details page.
Details page shows more specific information based on the Kubernetes provider
(either native or Enterprise PKS) of the cluster, which provides following
functionalities:

* Navigate back to landing page from the top navigation bar.
* Download `kubectl` configuration from the button to the right of cluster title.
* View General and Nodes information of native cluster. Info and Details are sub-sections containing cluster-centric and vCD/CSE related attributes.
* View General information of Enterprise PKS cluster.