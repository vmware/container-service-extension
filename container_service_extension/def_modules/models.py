# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple

DefInterface = namedtuple('DefInterface', ['name', 'id', 'vendor', 'nss',
                                           'version', 'readonly'])

DefEntityType = namedtuple('DefEntityType',
                           ['name', 'description', 'id', 'vendor','nss',
                            'version', 'externalId', 'schema', 'interfaces',
                            'readonly'])









