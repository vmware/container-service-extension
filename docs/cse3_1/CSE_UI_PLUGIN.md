---
layout: default
title: Kubernetes Container Clusters UI plugin for VCD
---

# Kubernetes Container Clusters UI plugin for VCD

VCD 10.3 comes with a Kubernetes Container Clusters UI plugin 3.0 out of the box. 

*Refer to [Compatibility Matrix](CSE31.html#cse31-compatibility-matrix) and
[Kubernetes Container Clusters UI plugin 3.0.0](https://docs.vmware.com/en/VMware-Cloud-Director/10.3/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-F8F4B534-49B2-43B2-AEEE-7BAEE8CE1844.html) documentation*

## Overview

For VCD versions before 10.2, Kubernetes Container Clusters UI plugin 1.0.3 can be used with CSE 3.0 to manage Kubernetes Clusters directly from VCD UI

## Get Kubernetes Container Clusters UI plugin

The v1.0.3 plugin binary can be downloaded from [here](https://github.com/vmware/container-service-extension/raw/master/cse_ui/1.0.3/container-ui-plugin.zip).

---

## Register and publish Kubernetes Container Clusters UI plugin

**Via VCD UI portal**

To register the plugin, upload `container-ui-plugin.zip` to VCD through `Customize Portal`
option in the navigation menu of VCD Service Provider view. Then follow the
standard steps of publishing an UI plugin. After registration, refresh the page.
There should be a `Kubernetes Container Clusters` option in the navigation menu.

To unregister the plugin, select the plugin in `Customize Portal` and click on
`DELETE` button.

## Access Control

Tenant users cannot register/unregister Kubernetes Container Clusters UI plugin, and they can only use the plugin once access has been granted by Service Provider.
Service Providers can enable/disable Kubernetes Container Clusters UI plugin as well as manage access contorl to the plugin.

## Enable/Disable plugin

On `Customize Portal` page, select `Container UI plugin`, and click on the `ENABLE` or `DISABLE` button.
Disabling the plugin will make the plugin inaccessible for both providers and tenants

## Access control for tenants

On `Customize Portal` page, select `Container UI plugin`, and click on the `PUBLISH` button. . In the wizard, customize the scope to publish to. To remove plugin access from specific tenants, un-select them from the scope and click publish.

---

## Functionality

### Landing Page

Select `Kubernetes Container Clusters` in the navigation menu to access the landing page.
A list of Kubernetes clusters created by Container Service Extension (CSE) will be displayed, along with some basic cluster information.

**Provider View**

Service providers can view all clusters in all organizations

**Tenant View**

Tenants can only view clusters in their organization that they have visibility for

**Common Roles**

* Organization Administrator: can view all clusters in the organization
* Catalog Author, vApp User and Console Access Only: can view clusters
  created by catalog authors
* vApp Author: can view clusters they own

Upon clicking on the cluster name, users can view the details page of the corresponding cluster.

**Cluster Creation**

Clicking the `NEW` button on the top left will open the cluster creation wizard.

**Cluster Deletion**

Select a cluster in the datagrid, and click the `DELETE` button on the top left.

### Cluster Info Page

Clicking on the cluster name will redirect you to its info page.
This info page contains the following functionalities:

* Navigate back to the landing page using the top navigation bar
* Download the cluster's kube config (to be used with `kubectl`) using the button on the right of the cluster name.
* View cluster information. **Info** section contains cluster-specific details, while **Details** section contains VCD/CSE details.
* Add new worker nodes to Native clusters. Removing worker nodes from native clusters is not supported in Kubernetes Container Clusters UI plugin 1.0.3

---

## Known Issues

**Creating a cluster using Kubernetes Container Clusters UI plugin as system administrator in a large-scale VCD (many orgs, org vdcs, networks, etc) will fail**

When trying to create cluster as a system administrator user, datagrids in cluster create wizard will fail to load, preventing cluster creation. (Error will be an extension timeout error).
This is because plugin 1.0.3 is not optimized to fetch VCD entities (orgs, ovdcs, networks, etc) at large scale (Tested in an environment with 80+ orgs/ovdcs/networks). The request will overload CSE Server and fail to complete.

Workaround: If system administrator must create a cluster in a large-scale VCD environment, CSE CLI should be used instead.

---

**Re-registering Kubernetes Container Clusters UI plugin with VCD fails**

If the beta version of CSE UI plugin is already registered with VCD, trying to
upgrade it via CSE cli or VCD UI will fail. Right now, the only way to update
the UI plugin is to de-register/delete it and then re-install using the new
zip file. Additionally, the provider will need to re-publish the plugin to all
the tenants that were previously given access to the CSE UI plugin.

---

**Kubernetes Container Clusters UI plugin landing page on VCD UI perpetually shows a spinning wheel**

If CSE server is inaccessible/down, on VCD UI's CSE landing page, user only
sees the loading spinner instead of an error message.

Workaround: Make sure CSE server is running.

---

**Cluster operations fail silently on UI**

On clicking `confirm` in cluster creation/deletion wizards/confirmation message
boxes, user does not immediately get to know if the plugin successfully sent
the request, or if CSE Server successfully received the same. Form validation
and HTTP error display is not implemented in Kubernetes Container Clusters UI plugin 1.0.3

---

**Enterprise PKS cluster creation fails from UI**

If CSE is enabled with Enterprise PKS but OrgVDCs are not enabled with
Enterprise PKS as their k8s provider, Kubernetes Container Clusters UI plugin 1.0.3 will allow cluster creation operation on that OrgVDC, but the operation will eventually fail. This behavior is as designed.

*Workaround:* - Enable the OrgVDC explicitly for Enterprise PKS cluster
deployment via the following command

```sh
>vcd cse ovdc enable [ovdc name] -k 'ent-pks' -o [Org Name] -d [domain name] -p [plan name]
```
