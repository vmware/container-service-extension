#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from collections import namedtuple

class PvdcResourcePoolPathInfo(namedtuple("PvdcResourcePoolPathInfo", 'name, vc, datacenter, cluster, rp_path')):
    """
    Immutable class representing Provider vDC related information for PKS setup.
    """
    def __str__(self):
        return "class:{c}, name : {name}, vc : {vc}, datacenter: {datacenter}, cluster : {cluster}," \
               " rp_path : {rp_path}".format(c=PvdcResourcePoolPathInfo.__name__,
                                             name = self.name,
                                             vc = self.vc,
                                             datacenter= self.datacenter,
                                             cluster= self.cluster,
                                             rp_path= self.rp_path)