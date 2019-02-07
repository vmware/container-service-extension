# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


# CSE SERVICE
# used for registering CSE to vCD as an api extension service.
CSE_SERVICE_NAME = 'cse'
CSE_SERVICE_NAMESPACE = 'cse'

# DEPLOY RIGHTS
# used by authorization framework to weed out unauthorized calls.
CSE_NATIVE_DEPLOY_RIGHT_NAME = 'CSE NATIVE DEPLOY RIGHT'
CSE_NATIVE_DEPLOY_RIGHT_DESCRIPTION = 'Right necessary to deploy kubernetes ' \
    'cluster via vCD apis in CSE'
CSE_NATIVE_DEPLOY_RIGHT_CATEGORY = 'cseRight'
CSE_NATIVE_DEPLOY_RIGHT_BUNDLE_KEY = 'cseBundleKey'
CSE_PKS_DEPLOY_RIGHT_NAME = 'PKS DEPLOY RIGHT'
CSE_PKS_DEPLOY_RIGHT_DESCRIPTION = 'Right necessary to deploy kubernetes ' \
    'cluster via vSphere apis in PKS'
CSE_PKS_DEPLOY_RIGHT_CATEGORY = 'pksRight'
CSE_PKS_DEPLOY_RIGHT_BUNDLE_KEY = 'pksBundleKey'
