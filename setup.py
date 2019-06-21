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
        (str(Path(cse_scripts_dir)), ['scripts/photon-v2/init.sh',
                                      'scripts/photon-v2/cust.sh',
                                      'scripts/photon-v2/mstr.sh',
                                      'scripts/photon-v2/node.sh',
                                      'scripts/photon-v2/nfsd.sh',
                                      'scripts/ubuntu-16.04/init.sh',
                                      'scripts/ubuntu-16.04/cust.sh',
                                      'scripts/ubuntu-16.04/mstr.sh',
                                      'scripts/ubuntu-16.04/node.sh',
                                      'scripts/ubuntu-16.04/nfsd.sh']),
        (str(Path('/')), ['LICENSE.txt', 'NOTICE.txt', osl]),
    ],
    pbr=True,
)
