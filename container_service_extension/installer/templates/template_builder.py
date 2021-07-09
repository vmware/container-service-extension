# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import FenceMode
from pyvcloud.vcd.client import NetworkAdapterType
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.vapp import VApp

from container_service_extension.common.constants.server_constants import TemplateBuildKey, TemplateScriptFile  # noqa: E501
from container_service_extension.common.utils.core_utils import download_file
from container_service_extension.common.utils.core_utils import NullPrinter
from container_service_extension.common.utils.core_utils import read_data_file
from container_service_extension.common.utils.pyvcloud_utils import catalog_item_exists  # noqa: E501
from container_service_extension.common.utils.pyvcloud_utils import get_org
from container_service_extension.common.utils.pyvcloud_utils import get_vdc
from container_service_extension.common.utils.pyvcloud_utils import upload_ova_to_catalog  # noqa: E501
from container_service_extension.common.utils.pyvcloud_utils import \
    wait_for_catalog_item_to_resolve
from container_service_extension.common.utils.vsphere_utils import get_vsphere
from container_service_extension.common.utils.vsphere_utils import vgr_callback
from container_service_extension.common.utils.vsphere_utils import wait_until_tools_ready  # noqa: E501
import container_service_extension.installer.templates.local_template_manager as ltm  # noqa: E501
from container_service_extension.logging.logger import NULL_LOGGER
import container_service_extension.server.compute_policy_manager as compute_policy_manager  # noqa: E501


# used for creating temp vapp
TEMP_VAPP_NETWORK_ADAPTER_TYPE = NetworkAdapterType.VMXNET3.value
TEMP_VAPP_FENCE_MODE = FenceMode.BRIDGED.value


def assign_placement_policy_to_template(client, cse_placement_policy,
                                        catalog_name, catalog_item_name,
                                        org_name, logger=NULL_LOGGER,
                                        log_wire=False, msg_update_callback=NullPrinter()):  # noqa: E501

    cpm = compute_policy_manager.ComputePolicyManager(client,
                                                      log_wire=log_wire)
    try:
        policy = compute_policy_manager.get_cse_vdc_compute_policy(
            cpm,
            cse_placement_policy,
            is_placement_policy=True)
        task = cpm.assign_vdc_placement_policy_to_vapp_template_vms(
            policy['href'],
            org_name,
            catalog_name,
            catalog_item_name)
        if task is not None:
            client.get_task_monitor().wait_for_success(task)
            msg = "Successfully tagged template " \
                  f"{catalog_item_name} with placement policy " \
                  f"{cse_placement_policy}."
        else:
            msg = f"{catalog_item_name} already tagged with" \
                  f" placement policy {cse_placement_policy}."
        msg_update_callback.general(msg)
        logger.info(msg)
    except Exception as err:
        msg = f"Failed to tag template {catalog_item_name} with " \
              f"placement policy {cse_placement_policy}. Error: {err}"
        msg_update_callback.error(msg)
        logger.error(msg)
        raise


class TemplateBuilder:
    """Builder calls for K8 templates."""

    def __init__(self, client, sys_admin_client, build_params, org=None,
                 vdc=None, ssh_key=None, logger=NULL_LOGGER,
                 msg_update_callback=NullPrinter(), log_wire=False):
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
        :param logging.Logger logger: logger object.
        :param utils.ConsoleMessagePrinter msg_update_callback:
            Callback object.
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
        self.template_name = build_params.get(TemplateBuildKey.TEMPLATE_NAME)  # noqa: E501
        self.template_revision = build_params.get(TemplateBuildKey.TEMPLATE_REVISION)  # noqa: E501
        self.ova_name = build_params.get(TemplateBuildKey.SOURCE_OVA_NAME)  # noqa: E501
        self.ova_href = build_params.get(TemplateBuildKey.SOURCE_OVA_HREF)  # noqa: E501
        self.ova_sha256 = build_params.get(TemplateBuildKey.SOURCE_OVA_SHA256)  # noqa: E501

        if org:
            self.org = org
            self.org_name = org.get_name()
        else:
            self.org_name = build_params.get(TemplateBuildKey.ORG_NAME)  # noqa: E501
            self.org = get_org(self.client, org_name=self.org_name)
        if vdc:
            self.vdc = vdc
            self.vdc.get_resource()  # to make sure vdc.resource is populated
            self.vdc_name = vdc.name
        else:
            self.vdc_name = build_params.get(TemplateBuildKey.VDC_NAME)  # noqa: E501
            self.vdc = get_vdc(self.client, vdc_name=self.vdc_name,
                               org=self.org)
        self.catalog_name = build_params.get(TemplateBuildKey.CATALOG_NAME)  # noqa: E501
        self.catalog_item_name = build_params.get(TemplateBuildKey.CATALOG_ITEM_NAME)  # noqa: E501
        self.catalog_item_description = \
            build_params.get(TemplateBuildKey.CATALOG_ITEM_DESCRIPTION)  # noqa: E501

        self.temp_vapp_name = build_params.get(TemplateBuildKey.TEMP_VAPP_NAME)  # noqa: E501
        self.temp_vm_name = build_params.get(TemplateBuildKey.TEMP_VM_NAME)  # noqa: E501
        self.cpu = build_params.get(TemplateBuildKey.CPU)
        self.memory = build_params.get(TemplateBuildKey.MEMORY)
        self.network_name = build_params.get(TemplateBuildKey.NETWORK_NAME)  # noqa: E501
        self.ip_allocation_mode = build_params.get(TemplateBuildKey.IP_ALLOCATION_MODE)  # noqa: E501
        self.storage_profile = build_params.get(TemplateBuildKey.STORAGE_PROFILE)  # noqa: E501
        self.cse_placement_policy = build_params.get(TemplateBuildKey.CSE_PLACEMENT_POLICY)  # noqa: E501
        self.remote_cookbook_version = build_params.get(TemplateBuildKey.REMOTE_COOKBOOK_VERSION)  # noqa: E501
        self.log_wire = log_wire

        if self.template_name and self.template_revision and \
                self.ova_name and self.ova_href and self.ova_sha256 and \
                self.org and self.org_name and self.vdc and self.vdc_name and \
                self.catalog_name and self.catalog_item_name and \
                self.catalog_item_description and self.temp_vapp_name and \
                self.temp_vm_name and self.cpu and self.memory and \
                self.network_name and self.ip_allocation_mode and \
                self.storage_profile:
            self._is_valid = True

    def _cleanup_old_artifacts(self):
        """Delete source ova, K8 template and temp vApp."""
        msg = "If K8 template, source ova file, and temporary vApp exists, " \
              "they will be deleted"
        self.msg_update_callback.info(msg)
        self.logger.info(msg)

        self._delete_catalog_item(item_name=self.catalog_item_name)
        self._delete_catalog_item(item_name=self.ova_name)
        self._delete_temp_vapp()

    def _delete_catalog_item(self, item_name):
        """Delete a catalog item.

        The catalog item to delete, is searched in the catalog specified via
        build_params.

        :param str item_name: name of the item to delete.
        """
        try:
            self.org.delete_catalog_item(name=self.catalog_name,
                                         item_name=item_name)
            wait_for_catalog_item_to_resolve(
                client=self.client, catalog_name=self.catalog_name,
                catalog_item_name=item_name, org=self.org)
            self.org.reload()

            msg = f"Deleted '{item_name}' from catalog '{self.catalog_name}'"
            self.msg_update_callback.general(msg)
            self.logger.info(msg)
        except EntityNotFoundException:
            pass

    def _delete_temp_vapp(self):
        """Delete the temp vApp for the K8 template."""
        try:
            msg = f"Deleting temporary vApp '{self.temp_vapp_name}'"
            self.msg_update_callback.general(msg)
            self.logger.info(msg)

            task = self.vdc.delete_vapp(self.temp_vapp_name, force=True)
            self.client.get_task_monitor().wait_for_success(task)
            self.vdc.reload()

            msg = f"Deleted temporary vApp '{self.temp_vapp_name}'"
            self.msg_update_callback.general(msg)
            self.logger.info(msg)
        except EntityNotFoundException:
            pass

    def _upload_source_ova(self):
        """Upload the base OS ova to catalog."""
        if catalog_item_exists(org=self.org, catalog_name=self.catalog_name,
                               catalog_item_name=self.ova_name):
            msg = f"Found ova file '{self.ova_name}' in catalog " \
                  f"'{self.catalog_name}'"
            self.msg_update_callback.general(msg)
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
            self.remote_cookbook_version,
            self.template_name,
            self.template_revision,
            TemplateScriptFile.INIT)
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

        msg = f"Creating vApp '{self.temp_vapp_name}'"
        self.msg_update_callback.info(msg)
        self.logger.info(msg)

        init_script = self._get_init_script()

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
            vm_name=self.temp_vm_name,
            hostname=self.temp_vm_name,
            storage_profile=self.storage_profile)
        task = vapp_sparse_resource.Tasks.Task[0]
        self.client.get_task_monitor().wait_for_success(task)
        self.vdc.reload()

        msg = f"Created vApp '{self.temp_vapp_name}'"
        self.msg_update_callback.general(msg)
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
        self.msg_update_callback.general(msg)
        self.logger.info(msg)

        cust_script_filepath = ltm.get_script_filepath(
            self.remote_cookbook_version,
            self.template_name,
            self.template_revision,
            TemplateScriptFile.CUST)
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
            self.msg_update_callback.error(
                "Failed VM customization. Check CSE install log")
            self.logger.error(f"Failed VM customization with error: {err}",
                              exc_info=True)
            raise

        if len(result) > 0:
            msg = f'Result: {result}'
            self.msg_update_callback.general_no_color(msg)
            self.logger.debug(msg)

            result_stdout = result[1].content.decode()
            result_stderr = result[2].content.decode()

            msg = 'stderr:'
            self.msg_update_callback.general_no_color(msg)
            self.logger.debug(msg)
            if len(result_stderr) > 0:
                self.msg_update_callback.general_no_color(result_stderr)
                self.logger.debug(result_stderr)

            msg = 'stdout:'
            self.msg_update_callback.general_no_color(msg)
            self.logger.debug(msg)
            if len(result_stdout) > 0:
                self.msg_update_callback.general_no_color(result_stdout)
                self.logger.debug(result_stdout)

        if len(result) == 0 or result[0] != 0:
            msg = "Failed VM customization"
            self.msg_update_callback.error(f"{msg}. Please check logs.")
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
        self.msg_update_callback.general(msg)
        self.logger.info(msg)

    def _capture_temp_vapp(self, vapp):
        """Capture a vapp as a template.

        :param pyvcloud.vcd.VApp vapp:
        """
        msg = f"Creating K8 template '{self.catalog_item_name}' from vApp " \
              f"'{self.temp_vapp_name}'"
        self.msg_update_callback.info(msg)
        self.logger.info(msg)

        # DEV NOTE: With api v33.0 and onwards, get_catalog operation will fail
        # for non admin users of an org which is not hosting the catalog, even
        # if the catalog is explicitly shared with the org in question. Please
        # use this method only for org admin and sys admins.
        catalog = self.org.get_catalog(self.catalog_name)
        try:
            msg = f"Shutting down vApp '{self.temp_vapp_name}'"
            self.msg_update_callback.info(msg)
            self.logger.info(msg)

            vapp.reload()
            task = vapp.shutdown()
            self.client.get_task_monitor().wait_for_success(task)
            vapp.reload()

            msg = f"Successfully shut down vApp '{self.temp_vapp_name}'"
            self.msg_update_callback.general(msg)
            self.logger.info(msg)
        except OperationNotSupportedException as err:
            if self.logger:
                self.logger.debug("Encountered error with shutting down vApp "
                                  f"'{self.temp_vapp_name}'" + str(err))

        msg = f"Capturing template '{self.catalog_item_name}' from vApp " \
              f"'{self.temp_vapp_name}'"
        self.msg_update_callback.info(msg)
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
        self.msg_update_callback.general(msg)
        self.logger.info(msg)

    def _tag_with_cse_placement_policy(self):
        """Tag the created template with placement policies if provided."""
        if not self.cse_placement_policy:
            msg = "Skipping tagging template with placement policy."
            self.msg_update_callback.info(msg)
            self.logger.debug(msg)
            return
        assign_placement_policy_to_template(
            self.client,
            self.cse_placement_policy,
            self.catalog_name,
            self.catalog_item_name,
            self.org_name,
            logger=self.logger,
            log_wire=self.log_wire,
            msg_update_callback=self.msg_update_callback)

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
                self._tag_with_cse_placement_policy()
                msg = f"Found template '{self.template_name}' at revision " \
                      f"{self.template_revision} in catalog " \
                      f"'{self.catalog_name}.'"
                self.msg_update_callback.general(msg)
                self.logger.info(msg)
                return
        else:
            self._cleanup_old_artifacts()

        self._upload_source_ova()
        vapp = self._create_temp_vapp()
        self._customize_vm(vapp, self.temp_vm_name)
        self._capture_temp_vapp(vapp)
        self._tag_with_cse_placement_policy()
        if not retain_temp_vapp:
            self._delete_temp_vapp()
