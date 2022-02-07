---
layout: default
title: Container UI Plugin for VCD
---

# Container UI Plugin for VCD

## Overview

From CSE 2.6.0 onwards, CSE users can use this plugin to interact with CSE Kubernetes clusters directly from VCD UI.

---

## Register and publish Container Ui Plugin

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

## Access Control

Tenant users themselves do not have the authority to register/unregister the
plugin. They can only use the plugin once access to it has been granted by
Service Provider. Service Provider has the authority to enable or disable and
manage access control to the UI Plugin.

## Enable/Disable plugin

From `Customize Portal`, choose the plugin to be enabled/disabled, then click on
`ENABLE` or `DISABLE` button. Once the plugin has been disabled and the page
has been refreshed, the plugin should be inaccessible from both provider and
tenant view.

## Access control for tenants

From `Customize Portal`, choose the plugin, click on `PUBLISH` button. Then in
the wizard, customize the scope to publish. To remove plugin access from
certain tenants, just un-select them from the scope and then publish.

---

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

---

## Known Issues

**Clarity datagrids in wizards that have more than 9 items do not render** ([github issue](https://github.com/vmware/container-service-extension/issues/648))

Fixed in: 1.0.2
Affected UI versions: 1.0.0, 1.0.1

Clarity has a bug where datagrids in wizards that have > 9 items have their height set to 0
Detailed here: https://github.com/vmware/clarity/issues/2364
This affects displaying networks, ovdcs, templates in cluster creation wizard.
UI plugin has implemented a workaround where we force set datagrid height to auto

---

**Networks are not displayed if the org vdc name has space(s)** ([github issue](https://github.com/vmware/container-service-extension/issues/625))

Fixed in: 1.0.2
Affected UI versions: 1.0.0, 1.0.1

Fixed in 1.0.2 by manually encoding the affected URLs before making the vcd api call

* Fix bug where plugin could not display networks from ovdcs with space(s) in the name
* Fix clarity bug where datagrids that have several items in them got their height set to 0

---

**Re-registering 2.6.0 GA CSE UI plugin with VCD doesn't work properly**

If the beta version of CSE UI plugin is already registered with VCD, trying to
upgrade it via CSE cli or VCD UI will fail. Right now, the only way to update
the UI plugin is to de-register/delete it and then re-install using the new
zip file. Additionally, the provider will need to re-publish the plugin to all
the tenants that were previously given access to the CSE UI plugin.

---

**CSE landing page on VCD UI perpetually shows a spinning wheel**

If CSE server is inaccessible/down, on VCD UI's CSE landing page, user only
sees the loading spinner instead of an error message. Workaround: Make sure CSE
server is up and running.

---

**Cluster operations fail silently on UI**

On clicking `confirm` in cluster creation/deletion wizards/confirmation message
boxes, user does not immediately get to know if the plugin successfully sent
the request, or if CSE Server successfully received the same. Form validation
and HTTP error display has not been implemented in CSE UI plugin yet.

---

**Enterprise PKS cluster creation fails from UI**

If CSE is enabled with Enterprise PKS but OrgVDCs are not enabled with
Enterprise PKS as their k8s provider, UI will allow cluster creation operation
on that OrgVDC, but the operation will eventually fail. This behavior is as
designed.

*Workaround:* - Enable the OrgVDC explicitly for Enterprise PKS cluster
deployment via the following command

```sh
>vcd cse ovdc enable [ovdc name] -k 'ent-pks' -o [Org Name] -d [domain name] -p [plan name]
```
