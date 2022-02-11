# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.task import Task, TaskStatus

from container_service_extension.common.constants.server_constants import LocalTemplateKey  # noqa: E501
from container_service_extension.common.constants.server_constants import TKGmTemplateKey  # noqa: E501
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.common.utils.thread_utils as thread_utils
import container_service_extension.exception.exceptions as e
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.telemetry_handler import record_user_action_telemetry  # noqa: E501
from container_service_extension.logging import logger
from container_service_extension.server import template_reader


@record_user_action_telemetry(cse_operation=CseOperation.TEMPLATE_LIST_CLIENT_SIDE)  # noqa: E501
def template_list(request_data, op_ctx):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = server_utils.get_server_runtime_config()
    templates = []

    for t in config.get_value_at('broker.templates'):
        template_name = t[LocalTemplateKey.NAME]
        template_revision = str(t[LocalTemplateKey.REVISION])

        templates.append({
            'catalog': config.get_value_at('broker.catalog'),
            'catalog_item': t[LocalTemplateKey.CATALOG_ITEM_NAME],
            'cni': t[LocalTemplateKey.CNI],
            'cni_version': t[LocalTemplateKey.CNI_VERSION],
            'deprecated': t[LocalTemplateKey.DEPRECATED],
            'description': t[LocalTemplateKey.DESCRIPTION].replace("\\n", ", "),  # noqa: E501
            'docker_version': t[LocalTemplateKey.DOCKER_VERSION],
            'is_default': 'No',
            'kind': t[LocalTemplateKey.KIND],
            'kubernetes': t[LocalTemplateKey.KUBERNETES],
            'kubernetes_version': t[LocalTemplateKey.KUBERNETES_VERSION],
            'name': template_name,
            'os': t[LocalTemplateKey.OS],
            'revision': template_revision
        })

    return sorted(templates, key=lambda i: (i['name'], i['revision']), reverse=True)  # noqa: E501


@record_user_action_telemetry(cse_operation=CseOperation.TEMPLATE_LIST_CLIENT_SIDE)  # noqa: E501
def tkgm_template_list(request_data, op_ctx):
    """Request handler for template list operation.

    :return: List of dictionaries with template info.
    """
    config = server_utils.get_server_runtime_config()
    tkgm_templates = []

    for t in config.get_value_at('broker.tkgm_templates'):
        tkgm_templates.append({
            'catalog': config.get_value_at('broker.catalog'),
            'catalog_item': t[TKGmTemplateKey.NAME],
            'cni': t[TKGmTemplateKey.CNI],
            'cni_version': t[TKGmTemplateKey.CNI_VERSION],
            'cse_version': t[TKGmTemplateKey.CSE_VERSION],
            'deprecated': None,
            'description': None,
            'docker_version': None,
            'container_runtime': t[TKGmTemplateKey.CONTAINER_RUNTIME],
            'container_runtime_version': t[TKGmTemplateKey.CONTAINER_RUNTIME_VERSION],  # noqa: E501
            'is_default': False,
            'kind': t[TKGmTemplateKey.KIND],
            'kubernetes': t[TKGmTemplateKey.KUBERNETES],
            'kubernetes_version': t[TKGmTemplateKey.KUBERNETES_VERSION],
            'name': t[TKGmTemplateKey.NAME],
            'os': f"{t[TKGmTemplateKey.OS]}-{t[TKGmTemplateKey.OS_VERSION]}",
            'revision': int(t[TKGmTemplateKey.REVISION])
        })

    return sorted(tkgm_templates, key=lambda i: (i['name'], i['revision']), reverse=True)  # noqa: E501


def reload_templates(request_data, op_ctx):
    """."""
    user_context = op_ctx.get_user_context(api_version=None)
    user_client = user_context.client

    if not user_client.is_sysadmin:
        raise e.UnauthorizedRequestError(
            error_message='Unauthorized to reload CSE native and TKG templates.'  # noqa: E501
        )

    org = vcd_utils.get_org(user_client, user_context.org_name)
    user_href = org.get_user(user_context.name).get('href')
    task = Task(user_client)
    task_resource = task.update(
        status=TaskStatus.RUNNING.value,
        namespace='vcloud.cse',
        operation="Reloading native templates.",
        operation_name='template operation',
        details='',
        progress=None,
        owner_href=user_context.org_href,
        owner_name=user_context.org_name,
        owner_type='application/vnd.vmware.vcloud.org+xml',
        user_href=user_href,
        user_name=user_context.name,
        org_href=user_context.org_href
    )
    task_href = task_resource.get('href')

    op_ctx.is_async = True
    _reload_templates_async(op_ctx, task_href)

    return {"task_href": task_href}


@thread_utils.run_async
def _reload_templates_async(op_ctx, task_href):
    user_context = None
    task = None
    user_href = None
    try:
        user_context = op_ctx.get_user_context(api_version=None)
        user_client = user_context.client
        org = vcd_utils.get_org(user_client, user_context.org_name)
        user_href = org.get_user(user_context.name).get('href')
        task = Task(user_client)

        server_config = server_utils.get_server_runtime_config()
        if not server_utils.is_no_vc_communication_mode():
            native_templates = \
                template_reader.read_native_template_definition_from_catalog(
                    config=server_config
                )
            server_config.set_value_at('broker.templates', native_templates)
            task.update(
                status=TaskStatus.RUNNING.value,
                namespace='vcloud.cse',
                operation="Finished reloading native templates.",
                operation_name='template reload',
                details='',
                progress=None,
                owner_href=user_context.org_href,
                owner_name=user_context.org_name,
                owner_type='application/vnd.vmware.vcloud.org+xml',
                user_href=user_href,
                user_name=user_context.name,
                org_href=user_context.org_href,
                task_href=task_href
            )
        else:
            msg = "Skipping loading k8s template definition from catalog " \
                  "since `No communication with VCenter` mode is on."
            logger.SERVER_LOGGER.info(msg)
            server_config.set_value_at('broker.templates', [])
            task.update(
                status=TaskStatus.RUNNING.value,
                namespace='vcloud.cse',
                operation=msg,
                operation_name='template reload',
                details='',
                progress=None,
                owner_href=user_context.org_href,
                owner_name=user_context.org_name,
                owner_type='application/vnd.vmware.vcloud.org+xml',
                user_href=user_href,
                user_name=user_context.name,
                org_href=user_context.org_href,
                task_href=task_href
            )

        task.update(
            status=TaskStatus.RUNNING.value,
            namespace='vcloud.cse',
            operation="Reloading TKG templates.",
            operation_name='template reload',
            details='',
            progress=None,
            owner_href=user_context.org_href,
            owner_name=user_context.org_name,
            owner_type='application/vnd.vmware.vcloud.org+xml',
            user_href=user_href,
            user_name=user_context.name,
            org_href=user_context.org_href,
            task_href=task_href
        )
        tkgm_templates = \
            template_reader.read_tkgm_template_definition_from_catalog(
                config=server_config
            )
        server_config.set_value_at('broker.tkgm_templates', tkgm_templates)
        task.update(
            status=TaskStatus.SUCCESS.value,
            namespace='vcloud.cse',
            operation="Finished reloading all templates.",
            operation_name='template reload',
            details='',
            progress=None,
            owner_href=user_context.org_href,
            owner_name=user_context.org_name,
            owner_type='application/vnd.vmware.vcloud.org+xml',
            user_href=user_href,
            user_name=user_context.name,
            org_href=user_context.org_href,
            task_href=task_href
        )
    except Exception:
        msg = "Error reloading templates."
        logger.SERVER_LOGGER.error(msg, exc_info=True)
        if task and user_context and user_href:
            task.update(
                status=TaskStatus.ERROR.value,
                namespace='vcloud.cse',
                operation=msg,
                operation_name='template reload',
                details='',
                progress=None,
                owner_href=user_context.org_href,
                owner_name=user_context.org_name,
                owner_type='application/vnd.vmware.vcloud.org+xml',
                user_href=user_href,
                user_name=user_context.name,
                org_href=user_context.org_href,
                task_href=task_href
            )
    finally:
        op_ctx.end()
