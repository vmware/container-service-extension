#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from collections import namedtuple

class PksInfo(namedtuple("PksInfo", 'name, host, port, uaac, vc')):
    """
    Immutable class representing PKS account information.
    """
    def __str__(self):
        return "class:{c}, name: {name}, host: {host}, port : {port}," \
               " uaac : {uaac}, vc : {vc}".format(c=PksInfo.__name__,
                                                  name= self.name,
                                                  host= self.host,
                                                  port= self.port,
                                                  uaac = self.uaac,
                                                  vc = self.vc)