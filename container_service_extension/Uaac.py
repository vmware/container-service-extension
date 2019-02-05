#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from collections import namedtuple

class Uaac(namedtuple("Uaac", 'port, secret, username')):
    """
    Immutable class representing information on UAAC from PKS configuration
    """
    def __str__(self):
        return "class:{c}, port : {port}," \
               " secret : {secret}, username : {username}".format(c=Uaac.__name__,
                                                  port= self.port,
                                                  secret = self.secret,
                                                  username = self.username)