# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import click
from pyvcloud.vcd.client import FenceMode
from pyvcloud.vcd.client import NetworkAdapterType
from pyvcloud.vcd.exceptions import EntityNotFoundException
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.vapp import VApp
from vcd_cli.utils import stdout

from container_service_extension.install_utils import download_file
from container_service_extension.install_utils import get_data_file
from container_service_extension.install_utils import get_vsphere
from container_service_extension.install_utils import vgr_callback
from container_service_extension.install_utils import wait_until_tools_ready
from container_service_extension.pyvcloud_utils import catalog_item_exists
from container_service_extension.pyvcloud_utils import get_org
from container_service_extension.pyvcloud_utils import get_vdc
from container_service_extension.pyvcloud_utils import upload_ova_to_catalog
from container_service_extension.pyvcloud_utils import \
    wait_for_catalog_item_to_resolve


class ConsoleMessageUpdateCallback():

    def general(self, msg):
        click.secho(msg, fg='green')

    def warning(self, msg):
        click.secho(msg, fg='yellow')

    def error(self, msg):
        click.secho(msg, fg='red')


# used for creating temp vapp
TEMP_VAPP_NETWORK_ADAPTER_TYPE = NetworkAdapterType.VMXNET3.value
TEMP_VAPP_FENCE_MODE = FenceMode.BRIDGED.value

class TemplateCreator():

    def __init__(self, client, msg_update_callback= None, logger=None):
        self.client = client
        self.msg_update_callback = msg_update_callback
        self.logger = logger

    def create_k8_template(config, template_config,
                           org=None, vdc=None ,ssh_key=None,
                           force_recreate=False, retain_temp_vapp=False):
        """Create a K8 template.

        :param bool force_recreate: if True and templates already exist in vCD, overwrites
            existing templates.
        :param bool retain_temp_vapp: if True, temporary vApp will not be captured or
            destroyed, so the user can ssh into the VM and debug.
        :param str ssh_key: public ssh key to place into the template vApp(s).
        :param pyvcloud.vcd.org.Org org: specific org to use.
        :param pyvcloud.vcd.vdc.VDC vdc: specific vdc to use.
        """
        # What is needed from config
        # broker : catalog org_name
        # broker : catalog vdc_name
        # broker : catalog_name

        # What is needed from template_config
        # catalog_item_name
        # temp_vapp_name
        # source_ova_name
        # source_ova_href
        # source_ova_sha256

        if org is None:
            org = get_org(client, org_name=config['broker']['org'])
        if vdc is None:
            vdc = get_vdc(client, vdc_name=config['broker']['vdc'], org=org)
        catalog_name = config['broker']['catalog']
        template_name = template_config['catalog_item']
        vapp_name = template_config['temp_vapp']
        ova_name = template_config['source_ova_name']

        if not force_recreate and catalog_item_exists(org, catalog_name, template_name):
            msg = f"Found template '{template_name}' in catalog '{catalog_name}'"
            if self.msg_update_callback:
                msg_update_callback.general(msg)
            if self.logger:
                self.logger.info(msg)
            return

        # if force_recreate flag is set, delete existing template/ova file/temp vapp
        if force_recreate:
            msg = f"--update flag set. If template, source ova file, " \
                  f"and temporary vApp exist, they will be deleted"
            click.secho(msg, fg='yellow')
            LOGGER.info(msg)
            try:
                org.delete_catalog_item(catalog_name, template_name)
                wait_for_catalog_item_to_resolve(client, catalog_name,
                                                 template_name, org=org)
                org.reload()
                msg = "Deleted vApp template"
                click.secho(msg, fg='green')
                LOGGER.info(msg)
            except EntityNotFoundException:
                pass
            try:
                org.delete_catalog_item(catalog_name, ova_name)
                wait_for_catalog_item_to_resolve(client, catalog_name, ova_name,
                                                 org=org)
                org.reload()
                msg = "Deleted ova file"
                click.secho(msg, fg='green')
                LOGGER.info(msg)
            except EntityNotFoundException:
                pass
            try:
                task = vdc.delete_vapp(vapp_name, force=True)
                stdout(task, ctx=ctx)
                client.get_task_monitor().wait_for_success(task)
                vdc.reload()
                msg = "Deleted temporary vApp"
                click.secho(msg, fg='green')
                LOGGER.info(msg)
            except EntityNotFoundException:
                pass

        # if needed, upload ova and create temp vapp
        msg = f"Creating template '{template_name}' in catalog '{catalog_name}'"
        click.secho(msg, fg='yellow')
        LOGGER.info(msg)
        temp_vapp_exists = True
        try:
            vapp = VApp(client, resource=vdc.get_vapp(vapp_name))
            msg = f"Found vApp '{vapp_name}'"
            click.secho(msg, fg='green')
            LOGGER.info(msg)
        except EntityNotFoundException:
            temp_vapp_exists = False

        if not temp_vapp_exists:
            if catalog_item_exists(org, catalog_name, ova_name):
                msg = f"Found ova file '{ova_name}' in catalog '{catalog_name}'"
                click.secho(msg, fg='green')
                LOGGER.info(msg)
            else:
                # download/upload files to catalog if necessary
                ova_filepath = f"cse_cache/{ova_name}"
                download_file(template_config['source_ova'], ova_filepath,
                              sha256=template_config['sha256_ova'], logger=LOGGER)
                upload_ova_to_catalog(client, catalog_name, ova_filepath, org=org,
                                      logger=LOGGER)

            vapp = _create_temp_vapp(ctx, client, vdc, config, template_config,
                                     ssh_key)

        # capture temp vapp as template
        msg = f"Creating template '{template_name}' from vApp '{vapp.name}'"
        click.secho(msg, fg='yellow')
        LOGGER.info(msg)
        self._capture_vapp_to_template(ctx, vapp, catalog_name, template_name,
                                       org=org, desc=template_config['description'],
                                       power_on=not template_config['cleanup'])
        msg = f"Created template '{template_name}' from vApp '{vapp_name}'"
        click.secho(msg, fg='green')
        LOGGER.info(msg)

        # delete temp vapp
        if not retain_temp_vapp::
            msg = f"Deleting vApp '{vapp_name}'"
            click.secho(msg, fg='yellow')
            LOGGER.info(msg)
            task = vdc.delete_vapp(vapp_name, force=True)
            stdout(task, ctx=ctx)
            vdc.reload()
            msg = f"Deleted vApp '{vapp_name}'"
            click.secho(msg, fg='green')
            LOGGER.info(msg)


    def _create_temp_vapp(ctx, client, vdc, config, template_config, ssh_key):
        """Handle temporary VApp creation and customization step of CSE install.

        Initializes and customizes VApp.

        :param click.core.Context ctx: click context object.
        :param pyvcloud.vcd.client.Client client:
        :param str ssh_key: ssh key to use in temporary VApp's VM. Can be None.

        :return: VApp object for temporary VApp.

        :rtype: pyvcloud.vcd.vapp.VApp

        :raises FileNotFoundError: if init/customization scripts are not found.
        :raises Exception: if VM customization fails.
        """
        vapp_name = template_config['temp_vapp']
        init_script = get_data_file(f"init-{template_config['name']}.sh",
                                    logger=LOGGER)
        if ssh_key is not None:
            init_script += \
                f"""
                mkdir -p /root/.ssh
                echo '{ssh_key}' >> /root/.ssh/authorized_keys
                chmod -R go-rwx /root/.ssh
                """
        msg = f"Creating vApp '{vapp_name}'"
        click.secho(msg, fg='yellow')
        LOGGER.info(msg)
        vapp = _create_vapp_from_config(client, vdc, config, template_config,
                                        init_script)
        msg = f"Created vApp '{vapp_name}'"
        click.secho(msg, fg='green')
        LOGGER.info(msg)
        msg = f"Customizing vApp '{vapp_name}'"
        click.secho(msg, fg='yellow')
        LOGGER.info(msg)
        cust_script = get_data_file(f"cust-{template_config['name']}.sh",
                                    logger=LOGGER)
        ova_name = template_config['source_ova_name']
        is_photon = True if 'photon' in ova_name else False
        _customize_vm(ctx, config, vapp, vapp.name, cust_script,
                      is_photon=is_photon)
        msg = f"Customized vApp '{vapp_name}'"
        click.secho(msg, fg='green')
        LOGGER.info(msg)

        return vapp

    def _create_vapp_from_config(client, vdc, config, template_config,
                                 init_script):
        """Create a VApp from a specific template config.

        This vApp is intended to be captured as a vApp template for CSE.
        Fence mode and network adapter type are fixed.

        :param pyvcloud.vcd.client.Client client:
        :param str init_script: initialization script for VApp.

        :return: initialized VApp object.

        :rtype: pyvcloud.vcd.vapp.VApp
        """
        vapp_sparse_resource = vdc.instantiate_vapp(
            template_config['temp_vapp'],
            config['broker']['catalog'],
            template_config['source_ova_name'],
            network=config['broker']['network'],
            fence_mode=TEMP_VAPP_FENCE_MODE,
            ip_allocation_mode=config['broker']['ip_allocation_mode'],
            network_adapter_type=TEMP_VAPP_NETWORK_ADAPTER_TYPE,
            deploy=True,
            power_on=True,
            memory=template_config['mem'],
            cpu=template_config['cpu'],
            password=None,
            cust_script=init_script,
            accept_all_eulas=True,
            vm_name=template_config['temp_vapp'],
            hostname=template_config['temp_vapp'],
            storage_profile=config['broker']['storage_profile'])
        task = vapp_sparse_resource.Tasks.Task[0]
        client.get_task_monitor().wait_for_success(task)
        vdc.reload()
        # we don't do lazy loading here using vapp_sparse_resource.get('href'),
        # because VApp would have an uninitialized attribute (vapp.name)
        vapp = VApp(client, resource=vapp_sparse_resource)
        vapp.reload()
        return vapp

    def _customize_vm(ctx, config, vapp, vm_name, cust_script, is_photon=False):
        """Customize a VM in a VApp using the customization script @cust_script.

        :param click.core.Context ctx: click context object. Needed to pass to
            stdout.
        :param pyvcloud.vcd.vapp.VApp vapp:
        :param str vm_name:
        :param str cust_script: the customization script to run on
        :param bool is_photon: True if the vapp was instantiated from
            a 'photon' ova file, False otherwise (False is safe even if
            the vapp is photon-based).

        :raises Exception: if unable to execute the customization script in
            VSphere.
        """
        callback = vgr_callback(prepend_msg='Waiting for guest tools, status: "')
        if not is_photon:
            vs = get_vsphere(config, vapp, vm_name, logger=LOGGER)
            wait_until_tools_ready(vapp, vs, callback=callback)

            vapp.reload()
            task = vapp.shutdown()
            stdout(task, ctx=ctx)
            vapp.reload()
            task = vapp.power_on()
            stdout(task, ctx=ctx)
            vapp.reload()

        vs = get_vsphere(config, vapp, vm_name, logger=LOGGER)
        wait_until_tools_ready(vapp, vs, callback=callback)
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
                callback=vgr_callback())
        except Exception as err:
            # TODO() replace raw exception with specific exception
            # unsure all errors execute_script_in_guest can result in
            # Docker TLS handshake timeout can occur when internet is slow
            click.secho("Failed VM customization. Check CSE install log", fg='red')
            LOGGER.error(f"Failed VM customization with error: {err}",
                         exc_info=True)
            raise

        # must reboot VM for some changes made during customization to take effect
        vs = get_vsphere(config, vapp, vm_name, logger=LOGGER)
        wait_until_tools_ready(vapp, vs, callback=callback)
        vapp.reload()
        task = vapp.shutdown()
        stdout(task, ctx=ctx)
        vapp.reload()
        task = vapp.power_on()
        stdout(task, ctx=ctx)
        vapp.reload()
        vs = get_vsphere(config, vapp, vm_name, logger=LOGGER)
        wait_until_tools_ready(vapp, vs, callback=callback)

        if len(result) > 0:
            msg = f'Result: {result}'
            click.echo(msg)
            LOGGER.debug(msg)
            result_stdout = result[1].content.decode()
            result_stderr = result[2].content.decode()
            msg = 'stderr:'
            click.echo(msg)
            LOGGER.debug(msg)
            if len(result_stderr) > 0:
                click.echo(result_stderr)
                LOGGER.debug(result_stderr)
            msg = 'stdout:'
            click.echo(msg)
            LOGGER.debug(msg)
            if len(result_stdout) > 0:
                click.echo(result_stdout)
                LOGGER.debug(result_stdout)
        if len(result) == 0 or result[0] != 0:
            msg = "Failed VM customization"
            click.secho(f"{msg}. Check CSE install log", fg='red')
            LOGGER.error(msg, exc_info=True)
            # TODO() replace raw exception with specific exception
            raise Exception(msg)

    def _capture_vapp_to_template(ctx, vapp, catalog_name, catalog_item_name,
                                  desc='', power_on=False, org=None, org_name=None):
        """Shutdown and capture existing VApp as a template in @catalog.

        VApp should have tools ready, or shutdown will fail, and VApp will be
        unavailable to be captured.

        :param click.core.Context ctx: click context object needed for stdout.
        :param pyvcloud.vcd.vapp.VApp vapp:
        :param str catalog_name:
        :param str catalog_item_name: catalog item name for the template.
        :param str desc: template description.
        :param bool power_on: if True, turns on VApp after capturing.
        :param pyvcloud.vcd.org.Org org: specific org to use.
        :param str org_name: specific org to use if @org is not given.
            If None, uses currently logged-in org from @vapp (vapp.client).

        :raises EntityNotFoundException: if the org could not be found.
        """
        if org is None:
            org = get_org(vapp.client, org_name=org_name)
        catalog = org.get_catalog(catalog_name)
        try:
            task = vapp.shutdown()
            stdout(task, ctx=ctx)
            vapp.reload()
        except OperationNotSupportedException:
            pass

        task = org.capture_vapp(catalog, vapp.href, catalog_item_name, desc,
                                customize_on_instantiate=True, overwrite=True)
        stdout(task, ctx=ctx)
        org.reload()

        if power_on:
            task = vapp.power_on()
            stdout(task, ctx=ctx)
            vapp.reload()
