# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import hashlib
import logging
import random
import socket
import ssl
import string
from urllib.parse import urlparse

from cachetools import LRUCache
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
from vsphere_guest_run.vsphere import VSphere

cache = LRUCache(maxsize=1024)

LOGGER = logging.getLogger('cse.utils')


def hex_chunks(s):
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def get_thumbprint(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    wrappedSocket = ssl.wrap_socket(sock)
    wrappedSocket.connect((host, port))
    der_cert_bin = wrappedSocket.getpeercert(True)
    thumb_sha1 = hashlib.sha1(der_cert_bin).hexdigest()
    wrappedSocket.close()
    return ':'.join(map(str, hex_chunks(thumb_sha1))).upper()


def random_word(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


def get_vsphere(config, vapp, vm_name):
    global cache
    vm_resource = vapp.get_vm(vm_name)
    vm_id = vm_resource.get('id')
    if vm_id not in cache:
        client_sysadmin = Client(
            uri=config['vcd']['host'],
            api_version=config['vcd']['api_version'],
            verify_ssl_certs=config['vcd']['verify'],
            log_headers=True,
            log_bodies=True)
        client_sysadmin.set_credentials(
            BasicLoginCredentials(config['vcd']['username'], 'System',
                                  config['vcd']['password']))

        vapp_sys = VApp(client_sysadmin, href=vapp.href)
        vm_resource = vapp_sys.get_vm(vm_name)
        vm_sys = VM(client_sysadmin, resource=vm_resource)
        vcenter_name = vm_sys.get_vc()
        platform = Platform(client_sysadmin)
        vcenter = platform.get_vcenter(vcenter_name)
        vcenter_url = urlparse(vcenter.Url.text)
        cache_item = {
            'hostname': vcenter_url.hostname,
            'username': vcenter.Username.text,
            'port': vcenter_url.port
        }
        for vc in config['vcs']:
            if vc['name'] == vcenter_name:
                cache_item['password'] = vc['password']
                break
        cache[vm_id] = cache_item
    else:
        LOGGER.debug('vCenter retrieved from cache: %s / %s' %
                     (vm_id, cache[vm_id]['hostname']))

    v = VSphere(cache[vm_id]['hostname'], cache[vm_id]['username'],
                cache[vm_id]['password'], cache[vm_id]['port'])

    return v
