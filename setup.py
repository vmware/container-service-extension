#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from setuptools import setup, find_packages
import pathlib

osl = 'open_source_license_container-service-extension_1.2.0_GA.txt'
cse_scripts_dir = '/container_service_extension_scripts'

setup(
    setup_requires=['pbr>=1.9', 'setuptools>=17.1'],
    package_data={'': ['swagger/swagger.yaml']},
    packages=find_packages(),
    data_files=[
        (str(pathlib.Path(cse_scripts_dir)), ['scripts/init-photon-v2.sh',
                                              'scripts/cust-photon-v2.sh',
                                              'scripts/mstr-photon-v2.sh',
                                              'scripts/node-photon-v2.sh',
                                              'scripts/init-ubuntu-16.04.sh',
                                              'scripts/cust-ubuntu-16.04.sh',
                                              'scripts/mstr-ubuntu-16.04.sh',
                                              'scripts/node-ubuntu-16.04.sh',
                                              'scripts/nfsd-ubuntu-16.04.sh']),
        (str(pathlib.Path('.')), ['LICENSE.txt',
                                  'NOTICE.txt',
                                  osl]),
    ],
    pbr=True,
)
