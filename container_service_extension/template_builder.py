# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import FenceMode
from pyvcloud.vcd.client import NetworkAdapterType
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.vapp import VApp

import container_service_extension.local_template_manager as ltm
from container_service_extension.pyvcloud_utils import catalog_item_exists
from container_service_extension.pyvcloud_utils import get_org
from container_service_extension.pyvcloud_utils import get_vdc
from container_service_extension.pyvcloud_utils import upload_ova_to_catalog
from container_service_extension.pyvcloud_utils import \
    wait_for_catalog_item_to_resolve
from container_service_extension.server_constants import ScriptFile
from container_service_extension.utils import download_file
from container_service_extension.utils import read_data_file
from container_service_extension.vsphere_utils import get_vsphere
from container_service_extension.vsphere_utils import vgr_callback
from container_service_extension.vsphere_utils import wait_until_tools_ready


# used for creating temp vapp
TEMP_VAPP_NETWORK_ADAPTER_TYPE = NetworkAdapterType.VMXNET3.value
TEMP_VAPP_FENCE_MODE = FenceMode.BRIDGED.value
TEMP_VAPP_VM_NAME = 'Temp-vm'


class TemplateBuilder():
    """Builder calls for K8 templates."""

    def __init__(self, client, sys_admin_client, build_params, org=None,
                 vdc=None, ssh_key=None, logger=None,
                 msg_update_callback=None):
        """.

        :param pyvcloud.vcd.Client client:
        :param pyvcloud.vcd.Client sys_admin_client:
        :param dict build_params:
        :param pyvcloud.vcd.org.Org org: specific org to use. Will override the
            org_name specified in build_params, can be used to save few vCD
            calls to create the Org object.
        :param pyvcloud.vcd.vdc.VDC vdc: specific vdc to use. Will override the
            vdc_name specified in build_params, can be used to save few vCD
            calls to create the Vdc object.
        :param str ssh_key: public ssh key to place into the template vApp(s).
        :param logging.Logger logger: optional logger to log with.
        :param utils.ConsoleMessagePrinter msg_update_callback: Callback object
            that writes messages onto console.
        """
        self._is_valid = False

        self.client = client
        self.sys_admin_client = sys_admin_client
        self.ssh_key = ssh_key
        self.logger = logger
        self.msg_update_callback = msg_update_callback

        if self.client is None or self.sys_admin_client is None:
            return

        # validate and populate required fields
        self.template_name = build_params.get('template_name')
        self.template_revision = build_params.get('template_revision')
        self.ova_name = build_params.get('source_ova_name')
        self.ova_href = build_params.get('source_ova_href')
        self.ova_sha256 = build_params.get('source_ova_sha256')

        if org:
            self.org = org
            self.org_name = org.get_name()
        else:
            self.org_name = build_params.get('org_name')
            self.org = get_org(self.client, org_name=self.org_name)
        if vdc:
            self.vdc = vdc
            self.vdc.get_resource()  # to make sure vdc.resource is populated
            self.vdc_name = vdc.name
        else:
            self.vdc_name = build_params.get('vdc_name')
            self.vdc = get_vdc(self.client, vdc_name=self.vdc_name,
                               org=self.org)
        self.catalog_name = build_params.get('catalog_name')
        self.catalog_item_name = build_params.get('catalog_item_name')
        self.catalog_item_description = \
            build_params.get('catalog_item_description')

        self.temp_vapp_name = build_params.get('temp_vapp_name')
        self.cpu = build_params.get('cpu')
        self.memory = build_params.get('memory')
        self.network_name = build_params.get('network_name')
        self.ip_allocation_mode = build_params.get('ip_allocation_mode')
        self.storage_profile = build_params.get('storage_profile')

        if self.template_name and self.template_revision and \
                self.ova_name and self.ova_href and self.ova_sha256 and \
                self.org and self.org_name and self.vdc and self.vdc_name and \
                self.catalog_name and self.catalog_item_name and \
                self.catalog_item_description and self.temp_vapp_name and \
                self.cpu and self.memory and self.network_name and \
                self.ip_allocation_mode and self.storage_profile:
            self._is_valid = True

    def _cleanup_old_artifacts(self):
        """Delete source ova, K8 template and temp vApp."""
        msg = "If K8 template, source ova file, and temporary vApp exists, " \
              "they will be deleted"
        if self.msg_update_callback:
            self.msg_update_callback.info(msg)
        if self.logger:
            self.logger.info(msg)

        self._delete_catalog_item(item_name=self.catalog_item_name)
        self._delete_catalog_item(item_name=self.ova_name)
        self._delete_temp_vapp()

    def _delete_catalog_item(self, item_name):
        """Delete a catalog item.

        The catalog item to delete, is searched in the catalog specified via
        build_params.

        :param str item_name: name of the item to delete.
        :param str item_type
        """
        try:
            self.org.delete_catalog_item(name=self.catalog_name,
                                         item_name=item_name)
            wait_for_catalog_item_to_resolve(
                client=self.client, catalog_name=self.catalog_name,
                catalog_item_name=item_name, org=self.org)
            self.org.reload()

            msg = f"Deleted '{item_name}' from catalog '{self.catalog_name}'"
            if self.msg_update_callback:
                self.msg_update_callback.general(msg)
            if self.logger:
                self.logger.info(msg)
        except EntityNotFoundException:
            pass

    def _delete_temp_vapp(self):
        """Delete the temp vApp for the K8 template."""
        try:
            msg = f"Deleting temporary vApp '{self.temp_vapp_name}'"
            if self.msg_update_callback:
                self.msg_update_callback.general(msg)
            if self.logger:
                self.logger.info(msg)

            task = self.vdc.delete_vapp(self.temp_vapp_name, force=True)
            self.client.get_task_monitor().wait_for_success(task)
            self.vdc.reload()

            msg = f"Deleted temporary vApp '{self.temp_vapp_name}'"
            if self.msg_update_callback:
                self.msg_update_callback.general(msg)
            if self.logger:
                self.logger.info(msg)
        except EntityNotFoundException:
            pass

    def _upload_source_ova(self):
        """Upload the base OS ova to catalog."""
        if catalog_item_exists(org=self.org, catalog_name=self.catalog_name,
                               catalog_item_name=self.ova_name):
            msg = f"Found ova file '{self.ova_name}' in catalog " \
                  f"'{self.catalog_name}'"
            if self.msg_update_callback:
                self.msg_update_callback.general(msg)
            if self.logger:
                self.logger.info(msg)
        else:
            ova_filepath = f"cse_cache/{self.ova_name}"
            download_file(url=self.ova_href, filepath=ova_filepath,
                          sha256=self.ova_sha256, logger=self.logger,
                          msg_update_callback=self.msg_update_callback)
            upload_ova_to_catalog(self.client, self.catalog_name, ova_filepath,
                                  org=self.org, logger=self.logger,
                                  msg_update_callback=self.msg_update_callback)

    def _get_init_script(self):
        """Read the initialization script from disk to create temp vApp.

        :return: content of the initialization script.

        :rtype: str
        """
        init_script_filepath = ltm.get_script_filepath(
            self.template_name, self.template_revision, ScriptFile.INIT)
        init_script = read_data_file(
            init_script_filepath, logger=self.logger,
            msg_update_callback=self.msg_update_callback)
        if self.ssh_key is not None:
            init_script += \
                f"mkdir -p /root/.ssh\n" \
                f"echo '{self.ssh_key}' >> /root/.ssh/authorized_keys\n" \
                f"chmod -R go-rwx /root/.ssh"
        return init_script

    def _create_temp_vapp(self):
        """Create the temporary vApp."""
        try:
            self._delete_temp_vapp()
        except EntityNotFoundException:
            pass

        init_script = self._get_init_script()

        msg = f"Creating vApp '{self.temp_vapp_name}'"
        if self.msg_update_callback:
            self.msg_update_callback.info(msg)
        if self.logger:
            self.logger.info(msg)

        vapp_sparse_resource = self.vdc.instantiate_vapp(
            self.temp_vapp_name,
            self.catalog_name,
            self.ova_name,
            network=self.network_name,
            fence_mode=TEMP_VAPP_FENCE_MODE,
            ip_allocation_mode=self.ip_allocation_mode,
            network_adapter_type=TEMP_VAPP_NETWORK_ADAPTER_TYPE,
            deploy=True,
            power_on=True,
            memory=self.memory,
            cpu=self.cpu,
            password=None,
            cust_script=init_script,
            accept_all_eulas=True,
            vm_name=TEMP_VAPP_VM_NAME,
            hostname=TEMP_VAPP_VM_NAME,
            storage_profile=self.storage_profile)
        task = vapp_sparse_resource.Tasks.Task[0]
        self.client.get_task_monitor().wait_for_success(task)
        self.vdc.reload()

        msg = f"Created vApp '{self.temp_vapp_name}'"
        if self.msg_update_callback:
            self.msg_update_callback.general(msg)
        if self.logger:
            self.logger.info(msg)

        return VApp(self.client, href=vapp_sparse_resource.get('href'))

    def _customize_vm(self, vapp, vm_name):
        """Customize a vm in a VApp using customization script.

        :param pyvcloud.vcd.vapp.VApp vapp:
        :param str vm_name:

        :raises Exception: if unable to execute the customization script in
            the vm.
        """
        msg = f"Customizing vApp '{self.temp_vapp_name}', vm '{vm_name}'"
        if self.msg_update_callback:
            self.msg_update_callback.general(msg)
        if self.logger:
            self.logger.info(msg)

        cust_script_filepath = ltm.get_script_filepath(
            self.template_name, self.template_revision, ScriptFile.CUST)
        cust_script = read_data_file(
            cust_script_filepath, logger=self.logger,
            msg_update_callback=self.msg_update_callback)

        vs = get_vsphere(self.sys_admin_client, vapp, vm_name,
                         logger=self.logger)
        callback = vgr_callback(
            prepend_msg='Waiting for guest tools, status: "',
            logger=self.logger,
            msg_update_callback=self.msg_update_callback)
        wait_until_tools_ready(vapp, vm_name, vs, callback=callback)
        password_auto = vapp.get_admin_password(vm_name)

        try:
            result = vs.execute_script_in_guest(
                vs.get_vm_by_moid(vapp.get_vm_moid(vm_name)),
                'root',
                password_auto,
                cust_script,
                target_file=None,
                wait_for_completion=True,
                wait_time=10,
                get_output=True,
                delete_script=True,
                callback=vgr_callback(
                    logger=self.logger,
                    msg_update_callback=self.msg_update_callback))
        except Exception as err:
            # TODO() replace raw exception with specific exception
            # unsure all errors execute_script_in_guest can result in
            # Docker TLS handshake timeout can occur when internet is slow
            if self.msg_update_callback:
                self.msg_update_callback.error(
                    "Failed VM customization. Check CSE install log")
            if self.logger:
                self.logger.error(f"Failed VM customization with error: {err}",
                                  exc_info=True)
            raise

        if len(result) > 0:
            msg = f'Result: {result}'
            if self.msg_update_callback:
                self.msg_update_callback.general_no_color(msg)
            if self.logger:
                self.logger.debug(msg)

            result_stdout = result[1].content.decode()
            result_stderr = result[2].content.decode()

            msg = 'stderr:'
            if self.msg_update_callback:
                self.msg_update_callback.general_no_color(msg)
            if self.logger:
                self.logger.debug(msg)
            if len(result_stderr) > 0:
                if self.msg_update_callback:
                    self.msg_update_callback.general_no_color(result_stderr)
                if self.logger:
                    self.logger.debug(result_stderr)

            msg = 'stdout:'
            if self.msg_update_callback:
                self.msg_update_callback.general_no_color(msg)
            if self.logger:
                self.logger.debug(msg)
            if len(result_stdout) > 0:
                if self.msg_update_callback:
                    self.msg_update_callback.general_no_color(result_stdout)
                if self.logger:
                    self.logger.debug(result_stdout)

        if len(result) == 0 or result[0] != 0:
            msg = "Failed VM customization"
            if self.msg_update_callback:
                self.msg_update_callback.error(f"{msg}. Please check logs.")
            if self.logger:
                self.logger.error(
                    f"{msg}\nResult start===\n{result}\n===Result end",
                    exc_info=True)
            # TODO: replace raw exception with specific exception
            raise Exception(f"{msg}; Result: {result}")

        # Do not reboot VM after customization. Reboot will generate a new
        # machine-id, and once we capture the VM, all VMs deployed from the
        # template will have the same machine-id, which can lead to
        # unpredictable behavior

        msg = f"Customized vApp '{self.temp_vapp_name}', vm '{vm_name}'"
        if self.msg_update_callback:
            self.msg_update_callback.general(msg)
        if self.logger:
            self.logger.info(msg)

    def _capture_temp_vapp(self, vapp):
        """Capture a vapp as a template.

        :param pyvcloud.vcd.VApp vapp:
        """
        msg = f"Creating K8 template '{self.catalog_item_name}' from vApp " \
              f"'{self.temp_vapp_name}'"
        if self.msg_update_callback:
            self.msg_update_callback.info(msg)
        if self.logger:
            self.logger.info(msg)

        # DEV NOTE: With api v33.0 and onwards, get_catalog operation will fail
        # for non admin users of an org which is not hosting the catalog, even
        # if the catalog is explicitly shared with the org in question. Please
        # use this method only for org admin and sys admins.
        catalog = self.org.get_catalog(self.catalog_name)
        try:
            msg = f"Shutting down vApp '{self.temp_vapp_name}'"
            if self.msg_update_callback:
                self.msg_update_callback.info(msg)
            if self.logger:
                self.logger.info(msg)

            vapp.reload()
            task = vapp.shutdown()
            self.client.get_task_monitor().wait_for_success(task)
            vapp.reload()

            msg = f"Successfully shut down vApp '{self.temp_vapp_name}'"
            if self.msg_update_callback:
                self.msg_update_callback.general(msg)
            if self.logger:
                self.logger.info(msg)
        except OperationNotSupportedException as err:
            if self.logger:
                self.logger.debug("Encountered error with shutting down vApp "
                                  f"'{self.temp_vapp_name}'" + str(err))

        msg = f"Capturing template '{self.catalog_item_name}' from vApp " \
              f"'{self.temp_vapp_name}'"
        if self.msg_update_callback:
            self.msg_update_callback.info(msg)
        if self.logger:
            self.logger.info(msg)

        task = self.org.capture_vapp(catalog, vapp.href,
                                     self.catalog_item_name,
                                     self.catalog_item_description,
                                     customize_on_instantiate=True,
                                     overwrite=True)
        self.client.get_task_monitor().wait_for_success(task)
        self.org.reload()

        msg = f"Created K8 template '{self.catalog_item_name}' from vApp " \
              f"'{self.temp_vapp_name}'"
        if self.msg_update_callback:
            self.msg_update_callback.general(msg)
        if self.logger:
            self.logger.info(msg)

    def build(self, force_recreate=False, retain_temp_vapp=False):
        """Create a K8 template.

        :param bool force_recreate: if True and template already exist in vCD,
            overwrites existing template.
        :param bool retain_temp_vapp: if True, temporary vApp will not be
            deleted, so the user can ssh into its vm and debug.
        """
        if not self._is_valid:
            raise Exception('Invalid params for building template.')

        if not force_recreate:
            if catalog_item_exists(org=self.org,
                                   catalog_name=self.catalog_name,
                                   catalog_item_name=self.catalog_item_name):
                msg = f"Found template '{self.template_name}' at revision " \
                      f"{self.template_revision} in catalog " \
                      f"'{self.catalog_name}.'"
                if self.msg_update_callback:
                    self.msg_update_callback.general(msg)
                if self.logger:
                    self.logger.info(msg)
                return
        else:
            self._cleanup_old_artifacts()

        self._upload_source_ova()
        vapp = self._create_temp_vapp()
        self._customize_vm(vapp, TEMP_VAPP_VM_NAME)
        self._capture_temp_vapp(vapp)
        if not retain_temp_vapp:
            self._delete_temp_vapp()
