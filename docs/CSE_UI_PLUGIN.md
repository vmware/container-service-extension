---
layout: default
title: CSE UI Plugin for VCD
---
# CSE UI plugin for VCD

## Overview
Along with CSE 2.6.0, we are releasing CSE UI plugin for VCD. Using this plugin,
CSE users would be able to interact with CSE Kubernetes clusters directly from
VCD UI.

## Getting the plugin
The v1.0.1 plugin binary can be downloaded from [here](https://github.com/vmware/container-service-extension/raw/master/cse_ui/1.0.1/container-ui-plugin.zip).

## Setting up the plugin
### Registering and publishing the plugin
**Method 1:** Via CSE server cli

To register the plugin, run
```sh
cse ui-plugin register [path to plugin zip file] -c [path to CSE config file] -s
```
To unregister the plugin, first we need to figure out the ID of the plugin.
List all installed plugins, and get ID of the CSE UI Plugin, by running
```sh
cse ui-plugin list -c [path to CSE config file] -s
```
Run the following command to remove the plugin from VCD.
```sh
cse ui-plugin deregister [ID] -c [path to CSE config file] -s
```

**Method 2:** Via VCD UI portal

To register the plugin, upload `container-ui-plugin.zip` to VCD through `Customize Portal`
option in the navigation menu of VCD Service Provider view. Then follow the
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

**Cluster Creation**

Users can also create new Kubernetes clusters by clicking on the `Add` link on
the top left. Clicking on this link will open up the `Create New Cluster`
wizard.

**Cluster Deletion**
Selecting a cluster on the landing page, displays an option to delete it on
top left.

### Details Page
Upon clicking on a container cluster, it takes you to it's details page.
Details page shows more specific information based on the Kubernetes provider
(either native or Enterprise PKS) of the cluster, which provides following
functionalities:

* Navigate back to landing page from the top navigation bar.
* Download `kubectl` configuration from the button to the right of cluster title.
* View General information of Enterprise PKS clusters.
* View General and Nodes information of native clusters. Info and Details are sub-sections containing cluster-centric and VCD/CSE related attributes.
* Add new worker nodes to native clusters. Removing worker nodes from native clusters is currently not supported via UI.