#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pathlib import Path

from setuptools import setup

osl = 'open_source_license_container-service-extension_3.0_GA.txt'

setup(
    setup_requires=['pbr>=1.9', 'setuptools>=17.1'],
    packages=['container_service_extension', 'cse_def_schema'],
    data_files=[
        (str(Path('/')), ['LICENSE.txt', 'NOTICE.txt', osl]),
    ],
    pbr=True,
)
