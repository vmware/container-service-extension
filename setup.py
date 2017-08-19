#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from setuptools import setup

setup(
    setup_requires=['pbr>=1.9', 'setuptools>=17.1'],
    package_data = {'':['swagger/swagger.yaml']},
    pbr=True,
)
