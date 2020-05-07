# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple

# DefInterface represents the schema of the defined entity interface
# https://<vcd>/cloudapi/1.0.0/interfaces
DefInterface = namedtuple('DefInterface', ['name', 'id', 'vendor', 'nss',
                                           'version', 'readonly'])

# DefEntityType represents the schema of the defined entity type
# https://<vcd>/cloudapi/1.0.0/entityTypes
DefEntityType = namedtuple('DefEntityType',
                           ['name', 'description', 'id', 'vendor', 'nss',
                            'version', 'externalId', 'schema', 'interfaces',
                            'readonly'])
