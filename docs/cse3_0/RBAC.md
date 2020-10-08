---
layout: default
title: Role Based Access Control
---

# Role Based Access Control (RBAC)
<a name="DEF-RBAC"></a>
## CSE 3.0 with vCD 10.2

CSE 3.0, when hooked to vCD >= 10.2, leverages the RBAC that comes with vCD's feature
[Defined Entity framework](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-0749DEA0-08A2-4F32-BDD7-D16869578F96.html).

_Note: The RBAC in this section refers to the roles and rights required for the tenants
 to perform the life cycle management of kubernetes clusters. It does not have 
 anything to do with the RBAC inside the kubernetes cluster itself._

<a name="grant-rights"></a>
### Grant rights to the tenant users
Native cluster operations are no longer gated by CSE API extension-specific 
rights as used in CSE 2.6.x. With the introduction of defined entity 
representation for native clusters, a new right bundle `cse:nativeCluster entitlement` 
gets created in Cloud Director during CSE Server installation, which is what 
guards the native cluster operations in CSE 3.0. The same is the case for Tkg clusters. 

The Provider needs to grant the Tkg cluster and Native cluster right bundles to the desired organizations and then grant the admin-level defined entity type rights to the Tenant Administrator role. This will enable the tenant administrator to grant the relevant cluster management rights to the desired tenant users. Users cannot view or deploy clusters unless they have one of the below-mentioned rights. Refer [How to manage defined entities](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-0749DEA0-08A2-4F32-BDD7-D16869578F96.html) for more details.

   * Right bundle for Tkg Cluster → `vmware:tkgcluster entitlement`
   * Right bundle for Native cluster → `cse:nativeCluster entitlement`
   * Five rights exist in each of the above right bundles. Note that any custom roles created with the below-mentioned rights need to at least have privileges of the pre-defined role of `vApp Author` in order to deploy native clusters.

       * Admin read
            * Tenant user with this right can view all the entities from the organization.
            * System administrator with this right can view all the entities of all the organizations.
       * Admin full control
            * Full control lets user not only to modify entities but also delete them
            * Tenant user with this right will have full control over all the entities of his organization.
            * System administrator with this right will have full control over all the entities of all the organizations.
       * Full control
            * Tenant user (say, cluster-admin role) with this right can modify and delete the entities he/she owns and also the shared entities with Full control ACL.
       * Modify
            * Tenant user (say, cluster-author role) with this right can modify the entities he/she owns and also the shared entities with Modify ACL.
       * Read
            * Tenant user (say, cluster-user role) with this right can view those entities he/she owns or shared.
   * Sample commands to clone pre-defined roles, grant rights to the custom roles, assign roles to the users.
        ```sh
        vcd role add-right cluster-org-admin 'cse:nativeCluster: View'  'cse:nativeCluster: Administrator View' 'cse:nativeCluster: Full Access' 'cse:nativeCluster: Modify' 'cse:nativeCluster: Administrator Full access' -o org1
        vcd role add-right cluster-admin 'cse:nativeCluster: View'   'cse:nativeCluster: Full Access' 'cse:nativeCluster: Modify'  -o org1
        vcd role add-right cluster-author 'cse:nativeCluster: View'    'cse:nativeCluster: Modify'  -o org1
        vcd role add-right cluster-user 'cse:nativeCluster: View'      -o org1

        vcd role add-right cluster-org-admin 'vmware:tkgcluster: View' 'vmware:tkgcluster: Administrator View' 'vmware:tkgcluster: Full Access' 'vmware:tkgcluster: Modify' 'vmware:tkgcluster: Administrator Full access' -o org1
        vcd role add-right cluster-admin 'vmware:tkgcluster: View' 'vmware:tkgcluster: Full Access' 'vmware:tkgcluster: Modify'  -o org1
        vcd role add-right cluster-author 'vmware:tkgcluster: View'  'vmware:tkgcluster: Modify'  -o org1
        vcd role add-right cluster-user 'vmware:tkgcluster: View'   -o org1

        vcd user create -E cluster-org-admin 'ca$hcow' cluster-org-admin
        vcd user create -E cluster-admin 'ca$hcow' cluster-admin 
        vcd user create -E cluster-author 'ca$hcow' cluster-author 
        vcd user create -E cluster-user 'ca$hcow' cluster-user  
        ```

### Sharing native clusters 
Tenant user need to perform below steps to share a native cluster to another user of the same organization.
1. Share the cluster vApp to the desired user with the desired ACL grant.
2. Share the corresponding defined entity to the desired user with the same level of ACL grant mentioned in step-1. Refer [Sharing defined entities](https://docs-staging.vmware.com/en/draft/VMware-Cloud-Director/10.2/VMware-Cloud-Director-Service-Provider-Admin-Portal-Guide/GUID-DAFF4CE9-B276-4A0B-99D9-22B985153236.html) for more details.

<a name="old RBAC"></a>
## CSE < 3.0 with vCD < 10.2
Below content describes the role based access control
(RBAC) mechanism through which administrators can administer restrictive
usage of CSE hooked to vCD versions < 10.2. It also explains the functioning of
 RBAC along with desired behaviors.


<a name="capability"></a>
### Capability

CSE 1.2.6 and above has the capability to restrict access to certain deployment
operations. To perform these operations, a user must have a certain right in
their assigned role. The following table lays out the right requirement for all
the restricted operations.

| Operation | Container Provider | Right | Introduced in |
| -| -| -| -|
| cluster create | Native(VCD) | {cse}:CSE NATIVE DEPLOY RIGHT | CSE 1.2.6 |
| cluster delete | Native(VCD) | {cse}:CSE NATIVE DEPLOY RIGHT | CSE 1.2.6 |
| cluster resize | Native(VCD) | {cse}:CSE NATIVE DEPLOY RIGHT | CSE 1.2.6 |
| node create | Native(VCD) | {cse}:CSE NATIVE DEPLOY RIGHT | CSE 1.2.6 |
| node delete | Native(VCD) | {cse}:CSE NATIVE DEPLOY RIGHT | CSE 1.2.6 |
| cluster create | Enterprise PKS | {cse}:PKS DEPLOY RIGHT | CSE 2.0.0b1 |
| cluster delete | Enterprise PKS | {cse}:PKS DEPLOY RIGHT | CSE 2.0.0b1 |
| cluster resize | Enterprise PKS | {cse}:PKS DEPLOY RIGHT | CSE 2.0.0b1 |

Note: Role Based Access Control feature is turned off by default.

<a name="functioning"></a>
### Functioning

Once the feature is turned on, any invocation of the restricted CSE
operations will cause the call to go through an authorization filter. In the
filter, CSE will look for certain right(s) in user's role. If the right(s)
required to perform the operation are found, then the call will go through
normally, else the call will fail and an appropriate error message will be
displayed on the client console.

<a name="enablement"></a>
### Enablement

When CSE v1.2.6 and above is installed (or upgraded from v1.2.5 and below), CSE
registers the above mentioned rights to vCloud Director. The rights are
automatically granted to the hidden 'System' organization in vCloud Director
and are visible to the Cloud administrator.

Cloud Administrator turns on the role based access control for CSE
- sets the 'enforce_authorization' flag to 'true' under 'service' section of
  the configuration file
- restarts the CSE server

Cloud administrator propagates the new right to Tenants, in order to grant
access for CSE operations.
```sh
vcd right add -o 'org name' '{cse}:CSE NATIVE DEPLOY RIGHT'
```
Cloud administrator can revoke access by removal of the right from the
concerned Tenants.
```sh
vcd right remove -o 'org name' '{cse}:CSE NATIVE DEPLOY RIGHT'
```
At this point, a user can't access restrictive operations, if the required
right is not propagated to his/her role.

Tenant administrators should add the new right (granted to them by Cloud Admin)
to existing roles in the organization, or create new roles with the new right.
Subsequently, they assign new or updated roles to users whom they wish to grant
access to the restricted CSE operations.
```sh
vcd role add-right 'role name' '{cse}:CSE NATIVE DEPLOY RIGHT'
```
There is no action required to be taken by tenant users.

<a name="faq"></a>
### FAQ
* I upgraded to CSE v1.2.6 and I do not want to leverage RBAC. Will the upgrade
  disrupt my user base?
    * CSE v1.2.6 does not turn RBAC on by default upon upgrade or
      fresh-install. It needs to be [explicitly enabled](#enablement).
* If my administrator does not grant me the new right, will I lose access to my
  previously deployed clusters?
    * You will still be able to access previously deployed clusters. You will
      not, however, be able to modify them.
