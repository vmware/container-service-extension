---
layout: default
title: Role Based Access Control
---

# Role Based Access Control (RBAC)
<a name="overview"></a>
## Overview

Till CSE 1.2.5, any authenticated vCloud Director user is able to leverage CSE
for Kubernetes Cluster deployments. There are no mechanics in CSE Service to 
restrict its usage. This page describes the new role based access
control (RBAC) mechanism through which administrators can administer
restrictive usage of CSE. It also explains the functioning of RBAC along with
desired behaviors.

<a name="capability"></a>
## Capability

CSE 1.2.6 has the capability to restrict access to certain deployment
operations. To perform these operations, a user must have a certain right in
their assigned role. The following table lays out the right requirement for all
the restricted operations.

| Operation      |  Right                        |
|:---------------|:------------------------------|
| cluster create | {cse}:CSE NATIVE DEPLOY RIGHT |
| cluster delete | {cse}:CSE NATIVE DEPLOY RIGHT |
| node create    | {cse}:CSE NATIVE DEPLOY RIGHT |
| node delete    | {cse}:CSE NATIVE DEPLOY RIGHT |

Note: Role Based Access Control feature is turned off by default.

<a name="functioning"></a>
## Functioning 

Once the feature is turned on, any invocation of the restricted CSE
operations will cause the call to go through an authorization filter. In the
filter, CSE will look for certain right(s) in user's role. If the right(s)
required to perform the operation are found, then the call will go through
normally, else the call will fail and an appropriate error message will be
displayed on the client console.

<a name="enablement"></a>
## Enablement

When CSE v1.2.6 is installed (or upgraded from v1.2.5 and below), CSE registers
the above mentioned right to vCloud Director. The right belongs to the hidden
'System' organization in vCloud Director and the Cloud administrator has the
visibility of it.

Cloud Administrator turns on the role based access control for CSE
- sets the 'enable_authorization' flag to 'true' under 'service' section of the
  configuration file
- restarts the CSE server

Cloud administrator propagates the new right to Tenants, in order to grant
access for CSE operations. 

    >vcd right add -o 'org name' "{cse}:CSE NATIVE DEPLOY RIGHT"

Cloud administrator can revoke access by removal of the right from the
concerned Tenants.

    >vcd right remove -o 'org name' "{cse}:CSE NATIVE DEPLOY RIGHT"

At this point, a user can't access restrictive operations, if the required
right is not propagated to his/her role.

Tenant administrators should add the new right (granted to them by Cloud admin)
to existing roles in the organization, or create new roles with the new right.
Subsequently, they assign new or updated roles to users whom they wish to grant
access to the restricted CSE operations.

    >vcd role add-right 'role name' "{cse}:CSE NATIVE DEPLOY RIGHT"

There is no action required on tenant users.

<a name="faq"></a>
## FAQ
* I upgraded to CSE v1.2.6 and I do not want to leverage RBAC. Will the upgrade
  disrupt my userbase?
    * CSE v1.2.6 does not turn RBAC on by default upon upgrade or
      fresh-install. It needs to be [explicitly enabled](#enablement).
* If my administrator does not grant me the new right, will I lose access to my
  previously deployed clusters?
    * You will still be able to access previously deployed clusters. You will
      not be able to modify them.