#! /usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json
import time, datetime, os, sys
from pyvcloud.vcloudair import VCA
from pyvcloud.system import System
from pyvcloud.helper.CommonUtils import convertPythonObjToStr

host = sys.argv[1]
username = 'administrator'
password = sys.argv[2]
org = 'System'
org_url = 'https://%s/cloud' % host
verify = False
log = True
version = '5.6'
extension_name = sys.argv[3]

vca = VCA(host=host, username=username, service_type='vcd',
          version=version, verify=verify, log=log)

result = vca.login(password=password, org=org, org_url=org_url)
print('connected: %s' % result)

system = System(session=vca.vcloud_session, verify=verify, log=log)

patterns = ['/cluster', '/cluster/.*', '/cluster/.*/.*']
result = system.register_extension(extension_name, extension_name,
                                   extension_name, patterns)
print(result)

extension = system.get_extension(extension_name)
if extension == None:
    print('extension %s not found' % extension_name)
else:
    print(extension.attrib['name'])
