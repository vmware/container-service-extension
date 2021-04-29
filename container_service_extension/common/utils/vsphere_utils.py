# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Contains utility methods for interacting with vSphere."""

from urllib.parse import urlparse

from cachetools import LRUCache
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
from vsphere_guest_run.vsphere import VSphere

from container_service_extension.common.utils.core_utils import NullPrinter
from container_service_extension.logging.logger import NULL_LOGGER

cache = LRUCache(maxsize=1024)
vsphere_list = []


def populate_vsphere_list(vcs):
    """Populate the global variable holding info on vCenter servers.

    This method must be called before a call to get_vsphere.

    :param list vcs: list of dictionaries, where each dictionary hold the name,
    admin username and password of a vCenter server.
    """
    global vsphere_list
    vsphere_list = vcs


def get_vsphere(sys_admin_client, vapp, vm_name, logger=NULL_LOGGER):
    """Get the VSphere object for a specific VM inside a VApp.

    :param pyvcloud.vcd.client.Client sys_admin_client:
    :param pyvcloud.vcd.vapp.VApp vapp: VApp used to get the VM ID.
    :param str vm_name:
    :param logging.Logger logger: logger to log with.

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

    logger.debug(f"VM ID: {vm_id}, Hostname: {cache[vm_id]['hostname']}")

    return VSphere(cache[vm_id]['hostname'], cache[vm_id]['username'],
                   cache[vm_id]['password'], cache[vm_id]['port'])


def vgr_callback(prepend_msg='',
                 logger=NULL_LOGGER, msg_update_callback=NullPrinter()):
    """Create a callback function to use for vsphere-guest-run functions.

    :param str prepend_msg: string to prepend to all messages received from
        vsphere-guest-run function.
    :param logging.Logger logger: logger to use in case of error.
    :param utils.ConsoleMessagePrinter msg_update_callback: Callback object.

    :return: callback function to print messages received
        from vsphere-guest-run

    :rtype: function
    """
    def callback(message, exception=None):
        msg = f"{prepend_msg}{message}"
        msg_update_callback.general_no_color(msg)
        logger.info(msg)
        if exception is not None:
            msg_update_callback.error(
                f"vsphere-guest-run error: {exception}")
            logger.error("vsphere-guest-run error", exc_info=True)
    return callback


def wait_until_tools_ready(vapp, vm_name, vsphere, callback=vgr_callback()):
    """Blocking function to ensure that a vm has VMware Tools ready.

    :param pyvcloud.vcd.vapp.VApp vapp:
    :param str vm_name:
    :param vsphere_guest_run.vsphere.VSphere vsphere:
    :param function callback: a function to print out messages received from
        vsphere-guest-run functions. Function signature should be like:
        def callback(message, exception=None), where parameter 'message'
        is a string.
    """
    vsphere.connect()
    moid = vapp.get_vm_moid(vm_name)
    vm = vsphere.get_vm_by_moid(moid)
    vsphere.wait_until_tools_ready(vm, sleep=5, callback=callback)
