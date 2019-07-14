# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from urllib.parse import urlparse

from cachetools import LRUCache
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
from vsphere_guest_run.vsphere import VSphere


cache = LRUCache(maxsize=1024)
vsphere_list = []


def populate_vsphere_list(vcs):
    global vsphere_list
    vsphere_list = vcs


def get_vsphere(sys_admin_client, vapp, vm_name, logger=None):
    """Get the VSphere object for a specific VM inside a VApp.

    :param pyvcloud.vcd.vapp.VApp vapp: VApp used to get the VM ID.
    :param str vm_name:
    :param logging.Logger logger: optional logger to log with.

    :return: VSphere object for a specific VM inside a VApp

    :rtype: vsphere_guest_run.vsphere.VSphere
    """
    global cache
    global vsphere_list

    # get vm id from vm resource
    vm_id = vapp.get_vm(vm_name).get('id')
    if vm_id not in cache:
        # recreate vapp with sys admin client
        vapp = VApp(sys_admin_client, href=vapp.href)
        vm_resource = vapp.get_vm(vm_name)
        vm_sys = VM(sys_admin_client, resource=vm_resource)
        vcenter_name = vm_sys.get_vc()
        platform = Platform(sys_admin_client)
        vcenter = platform.get_vcenter(vcenter_name)
        vcenter_url = urlparse(vcenter.Url.text)
        cache_item = {
            'hostname': vcenter_url.hostname,
            'port': vcenter_url.port
        }
        if not vsphere_list:
            raise Exception("Global list of vSphere info not set.")

        for vc in vsphere_list:
            if vc['name'] == vcenter_name:
                cache_item['username'] = vc['username']
                cache_item['password'] = vc['password']
                break
        cache[vm_id] = cache_item

    if logger:
        logger.debug(f"VM ID: {vm_id}, Hostname: {cache[vm_id]['hostname']}")

    return VSphere(cache[vm_id]['hostname'], cache[vm_id]['username'],
                   cache[vm_id]['password'], cache[vm_id]['port'])


def vgr_callback(prepend_msg='', logger=None, msg_update_callback=None):
    """Create a callback function to use for vsphere-guest-run functions.

    :param str prepend_msg: string to prepend to all messages received from
        vsphere-guest-run function.
    :param logging.Logger logger: logger to use in case of error.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
        that writes messages onto console.

    :return: callback function to print messages received
        from vsphere-guest-run

    :rtype: function
    """
    def callback(message, exception=None):
        msg = f"{prepend_msg}{message}"
        if msg_update_callback:
            msg_update_callback.general_no_color(msg)
        if logger:
            logger.info(msg)
        if exception is not None:
            if msg_update_callback:
                msg_update_callback.error(
                    f"vsphere-guest-run error: {exception}")
            if logger:
                logger.error("vsphere-guest-run error", exc_info=True)
    return callback


def wait_until_tools_ready(vapp, vsphere, callback=vgr_callback()):
    """Blocking function to ensure that a VSphere has VMware Tools ready.

    :param pyvcloud.vcd.vapp.VApp vapp:
    :param vsphere_guest_run.vsphere.VSphere vsphere:
    :param function callback: a function to print out messages received from
        vsphere-guest-run functions. Function signature should be like this:
        def callback(message, exception=None), where parameter 'message'
        is a string.
    """
    vsphere.connect()
    moid = vapp.get_vm_moid(vapp.name)
    vm = vsphere.get_vm_by_moid(moid)
    vsphere.wait_until_tools_ready(vm, sleep=5, callback=callback)
