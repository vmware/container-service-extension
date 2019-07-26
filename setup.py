#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pathlib import Path

from setuptools import setup

osl = 'open_source_license_container-service-extension_2.0_GA.txt'
cse_scripts_dir = '/container_service_extension_scripts'

setup(
    setup_requires=['pbr>=1.9', 'setuptools>=17.1'],
    package_data={'': ['swagger/swagger.yaml']},
    packages=['container_service_extension'],
    data_files=[
        (str(Path('/')), ['LICENSE.txt', 'NOTICE.txt', osl]),
    ],
    pbr=True,
)
