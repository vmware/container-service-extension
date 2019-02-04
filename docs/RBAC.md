---
layout: default
title: Role Based Access Control for CSE
---

# Role Based Access Control (RBAC) for CSE
<a name="rbac"/>
## Overview

Till CSE v1.2.5, any authenticated vCD user was able to issue commands against
a CSE installation. There was no way to restrict access to CSE services at any
level (viz. Tentant, User, CSE operations). This page describes the new role
based access control mechanism in CSE, how to turn it on and in general how to
use the feature.

## What is RBAC

In CSE v1.2.6 we have restricted access to few core operations. To perform
these operations a user will need to have a certain right in their assigned
role. The following table lays out the right reqruiements for all the
restricted operations.

| Opeation       | Required right                |
|:---------------|:------------------------------|
| cluster create | {cse}:CSE NATIVE DEPLOY RIGHT |
| cluster delete | {cse}:CSE NATIVE DEPLOY RIGHT |
| node create    | {cse}:CSE NATIVE DEPLOY RIGHT |
| node delete    | {cse}:CSE NATIVE DEPLOY RIGHT |

Note: Out of box (on a fresh install/upgrade) the feature is turned off by
default.

## How it works?

Once the feature is turned on, any invocation of the the restricted CSE
operations will cause the call to go through an authorization filter. In the
filter, CSE will look for certain right(s) in user's role. If the right(s)
required to perform the operation are found, then the call will go through
normally, else the call will fail and an appropriate error message will be
displayed on the client console.

## What Cloud admin needs to do?

As soon as CSE v1.2.6 is installed (or upgraded from v1.2.5 and below). CSE
registers few rights to vCD. These rights end up in the hidden 'System'
organization in vCD. A Cloud admin will be able to see these new rights.

Cloud admins will need to award these new rights to Tenants, whom they wish to
grant access to restricted CSE operations.

>vcd right add -o <org name> "{cse}:CSE NATIVE DEPLOY RIGHT"

To turn on the feature, Cloud admin needs to flip the entry
'enable_authorization' under 'service' section of the configuration file to
'true', and then *restart* the CSE server. 

## What Tenant admin needs to do?

Once the RBAC feature is turned on a CSE server. Any user who doesn't have the
required rights in their role will be unable to perform the restricted operations.

A Tenant admin should add the new right(s) (granted to them by Cloud admin) to
existing roles in the organizaiton, or create new roles around these new
rights. And subsequently assign these new/updated roles to users whom they wish
to grant access to the restricted CSE operations.

  >vcd role add-right <role name> "{cse}:CSE NATIVE DEPLOY RIGHT"

## What Tenant users need to do?
There is no action required on tenant users.

## FAQ
* I just upgraded CSE to v1.2.6, I don't want RBAC, will the upgrade disrupt my userbase?
    * No, out of box CSE doesn't have RBAC turned on. It needs to be explitly turned on by a Cloud Admin.
* Tenant User - If my Tenant admin doesn't grant me the new rights, will I lose access to all my previously deployed cluster?
    * No, you can still access previously deployed clusters. But you won't be able to modify them.