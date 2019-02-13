# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import re
import threading
import traceback
import uuid

import click
import pkg_resources
from pyvcloud.vcd.client import _WellKnownEndpoint
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.client import VCLOUD_STATUS_MAP
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.task import Task
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vm import VM

from container_service_extension.abstract_broker import AbstractBroker
from container_service_extension.authorization import secure
from container_service_extension.cluster import add_nodes
from container_service_extension.cluster import delete_nodes_from_cluster
from container_service_extension.cluster import execute_script_in_nodes
from container_service_extension.cluster import get_cluster_config
from container_service_extension.cluster import get_master_ip
from container_service_extension.cluster import init_cluster
from container_service_extension.cluster import join_cluster
from container_service_extension.cluster import load_from_metadata
from container_service_extension.cluster import TYPE_MASTER
from container_service_extension.cluster import TYPE_NFS
from container_service_extension.cluster import TYPE_NODE
from container_service_extension.exceptions import ClusterAlreadyExistsError
from container_service_extension.exceptions import ClusterInitializationError
from container_service_extension.exceptions import ClusterJoiningError
from container_service_extension.exceptions import ClusterOperationError
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import MasterNodeCreationError
from container_service_extension.exceptions import NFSNodeCreationError
from container_service_extension.exceptions import NodeCreationError
from container_service_extension.exceptions import WorkerNodeCreationError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.ovdc_cache import OvdcCache
from container_service_extension.server_constants import \
    CSE_NATIVE_DEPLOY_RIGHT_NAME
from container_service_extension.utils import ACCEPTED
from container_service_extension.utils import connect_vcd_user_via_token
from container_service_extension.utils import ERROR_DESCRIPTION
from container_service_extension.utils import ERROR_MESSAGE
from container_service_extension.utils import ERROR_STACKTRACE
from container_service_extension.utils import error_to_json
from container_service_extension.utils import exception_handler
from container_service_extension.utils import get_server_runtime_config
from container_service_extension.utils import get_vcd_sys_admin_client
from container_service_extension.utils import OK

OP_CREATE_CLUSTER = 'create_cluster'
OP_DELETE_CLUSTER = 'delete_cluster'
OP_CREATE_NODES = 'create_nodes'
OP_DELETE_NODES = 'delete_nodes'

OP_MESSAGE = {
    OP_CREATE_CLUSTER: 'create cluster',
    OP_DELETE_CLUSTER: 'delete cluster',
    OP_CREATE_NODES: 'create nodes in cluster',
    OP_DELETE_NODES: 'delete nodes from cluster',
}

MAX_HOST_NAME_LENGTH = 25
ROLLBACK_FLAG = 'disable_rollback'


def spinning_cursor():
    while True:
        for cursor in '|/-\\':
            yield cursor


spinner = spinning_cursor()


def rollback(func):
    """Decorate to rollback on cluster and node creation failures.

    :param func: reference to the original function that is decorated

    :return: reference to the decorator wrapper
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (MasterNodeCreationError, WorkerNodeCreationError,
                NFSNodeCreationError, ClusterJoiningError,
                ClusterInitializationError):
            try:
                # arg[0] refers to the current instance of the broker thread
                broker_instance = args[0]  # param self
                if broker_instance.body[ROLLBACK_FLAG]:
                    broker_instance.cluster_rollback()
            except Exception as err:
                LOGGER.error(f"Failed to rollback cluster creation:{str(err)}")
        except NodeCreationError as e:
            try:
                broker_instance = args[0]
                node_list = e.node_names
                if broker_instance.body[ROLLBACK_FLAG]:
                    broker_instance.node_rollback(node_list)
            except Exception as err:
                LOGGER.error('Failed to rollback node creation:%s', str(err))
    return wrapper


def task_callback(task):
    message = '\x1b[2K\r{}: {}, status: {}'.format(
        task.get('operationName'), task.get('operation'), task.get('status'))
    if hasattr(task, 'Progress'):
        message += ', progress: %s%%' % task.Progress
    if task.get('status').lower() in [
            TaskStatus.QUEUED.value, TaskStatus.PENDING.value,
            TaskStatus.PRE_RUNNING.value, TaskStatus.RUNNING.value
    ]:
        message += ' %s ' % spinner.next()
    click.secho(message)


class DefaultBroker(AbstractBroker, threading.Thread):
    def __init__(self, headers, request_body):
        threading.Thread.__init__(self)
        self.headers = headers
        self.body = request_body

        self.tenant_client = None
        self.client_session = None
        self.tenant_info = None

        self.sys_admin_client = None

        self.task = None
        self.task_resource = None
        self.op = None
        self.cluster_name = None
        self.cluster_id = None
        self.daemon = False

    def _to_message(self, e):
        if hasattr(e, 'message'):
            return {'message': e.message}
        else:
            return {'message': str(e)}

    def update_task(self,
                    status,
                    message=None,
                    error_message=None,
                    stack_trace=''):
        if not self.tenant_client.is_sysadmin():
            stack_trace = ''

        if self.task is None:
            self.task = Task(self.sys_admin_client)

        if message is None:
            message = OP_MESSAGE[self.op]

        if self.task_resource is not None:
            task_href = self.task_resource.get('href')
        else:
            task_href = None

        self.task_resource = self.task.update(
            status=status.value,
            namespace='vcloud.cse',
            operation=message,
            operation_name=self.op,
            details='',
            progress=None,
            owner_href='urn:cse:cluster:%s' % self.cluster_id,
            owner_name=self.cluster_name,
            owner_type='application/vcloud.cse.cluster+xml',
            user_href=self.tenant_info['user_id'],
            user_name=self.tenant_info['user_name'],
            org_href=self.tenant_info['org_href'],
            task_href=task_href,
            error_message=error_message,
            stack_trace=stack_trace
        )

    def is_valid_name(self, name):
        """Validate that the cluster name against the pattern."""
        if len(name) > MAX_HOST_NAME_LENGTH:
            return False
        if name[-1] == '.':
            name = name[:-1]
        allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in name.split("."))

    def get_template(self, name=None):
        server_config = get_server_runtime_config()
        if name is None:
            if 'template' in self.body and self.body['template'] is not None:
                name = self.body['template']
            else:
                name = server_config['broker']['default_template']
        for template in server_config['broker']['templates']:
            if template['name'] == name:
                return template
        raise Exception('Template %s not found' % name)

    def run(self):
        LOGGER.debug('thread started op=%s' % self.op)
        if self.op == OP_CREATE_CLUSTER:
            self.create_cluster_thread()
        elif self.op == OP_DELETE_CLUSTER:
            self.delete_cluster_thread()
        elif self.op == OP_CREATE_NODES:
            self.create_nodes_thread()
        elif self.op == OP_DELETE_NODES:
            self.delete_nodes_thread()

    @exception_handler
    def list_clusters(self):
        result = {}
        result['body'] = []
        result['status_code'] = OK
        self._connect_tenant()
        clusters = load_from_metadata(self.tenant_client)
        result['body'] = clusters
        return result

    @exception_handler
    def get_cluster_info(self, name):
        """Get the info of the cluster.

        :param cluster_name: (str): Name of the cluster

        :return: (dict): Info of the cluster.
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK

        self._connect_tenant()
        clusters = load_from_metadata(self.tenant_client, name=name)
        if len(clusters) == 0:
            raise CseServerError('Cluster \'%s\' not found.' % name)
        vapp = VApp(self.tenant_client, href=clusters[0]['vapp_href'])
        vms = vapp.get_all_vms()
        for vm in vms:
            node_info = {
                'name': vm.get('name'),
                'ipAddress': ''
            }
            try:
                node_info['ipAddress'] = vapp.get_primary_ip(
                    vm.get('name'))
            except Exception:
                LOGGER.debug(
                    'cannot get ip address for node %s' % vm.get('name'))
            if vm.get('name').startswith(TYPE_MASTER):
                clusters[0].get('master_nodes').append(node_info)
            elif vm.get('name').startswith(TYPE_NODE):
                clusters[0].get('nodes').append(node_info)
            elif vm.get('name').startswith(TYPE_NFS):
                clusters[0].get('nfs_nodes').append(node_info)
        result['body'] = clusters[0]
        return result

    @exception_handler
    def get_node_info(self, cluster_name, node_name):
        """Get the info of a given node in the cluster.

        :param cluster_name: (str): Name of the cluster
        :param node_name: (str): Name of the node

        :return: (dict): Info of the node.
        """
        result = {}
        result['body'] = []
        result['status_code'] = OK
        self._connect_tenant()
        clusters = load_from_metadata(self.tenant_client,
                                      name=cluster_name)
        if len(clusters) == 0:
            raise CseServerError(f"Cluster \'{cluster_name}\' not found.")
        vapp = VApp(self.tenant_client, href=clusters[0]['vapp_href'])
        vms = vapp.get_all_vms()
        node_info = None
        for vm in vms:
            if (node_name == vm.get('name')):
                node_info = {
                    'name': vm.get('name'),
                    'numberOfCpus': '',
                    'memoryMB': '',
                    'status': VCLOUD_STATUS_MAP.get(int(vm.get('status'))),
                    'ipAddress': ''
                }
                if hasattr(vm, 'VmSpecSection'):
                    node_info[
                        'numberOfCpus'] = vm.VmSpecSection.NumCpus.text
                    node_info[
                        'memoryMB'] = \
                        vm.VmSpecSection.MemoryResourceMb.Configured.text
                try:
                    node_info['ipAddress'] = vapp.get_primary_ip(
                        vm.get('name'))
                except Exception:
                    LOGGER.debug('cannot get ip address '
                                 'for node %s' % vm.get('name'))
                if vm.get('name').startswith(TYPE_MASTER):
                    node_info['node_type'] = 'master'
                elif vm.get('name').startswith(TYPE_NODE):
                    node_info['node_type'] = 'node'
                elif vm.get('name').startswith(TYPE_NFS):
                    node_info['node_type'] = 'nfsd'
                    exports = self._get_nfs_exports(node_info['ipAddress'],
                                                    vapp,
                                                    vm)
                    node_info['exports'] = exports
        if node_info is None:
            raise CseServerError('Node \'%s\' not found in cluster \'%s\''
                                 % (node_name, cluster_name))
        result['body'] = node_info
        return result

    def _get_nfs_exports(self, ip, vapp, node):
        """Get the exports from remote NFS server (helper method).

        :param ip: (str): IP address of the NFS server
        :param vapp: (pyvcloud.vcd.vapp.VApp): The vApp or cluster
         to which node belongs
        :param node: (str): IP address of the NFS server
        :param node: (`lxml.objectify.StringElement`) object
        representing the vm resource.

        :return: (List): List of exports
        """
        # TODO(right template) find a right way to retrieve
        # the template from which nfs node was created.
        server_config = get_server_runtime_config()
        template = server_config['broker']['templates'][0]
        script = '#!/usr/bin/env bash\nshowmount -e %s' % ip
        result = execute_script_in_nodes(
            server_config, vapp, template['admin_password'],
            script, nodes=[node], check_tools=False)
        lines = result[0][1].content.decode().split('\n')
        exports = []
        for index in range(1, len(lines) - 1):
            export = lines[index].strip().split()[0]
            exports.append(export)
        return exports

    @exception_handler
    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def create_cluster(self):
        result = {}
        result['body'] = {}

        cluster_name = self.body['name']
        vdc_name = self.body['vdc']
        node_count = self.body['node_count']
        LOGGER.debug('About to create cluster %s on %s with %s nodes, sp=%s',
                     cluster_name, vdc_name, node_count,
                     self.body['storage_profile'])
        result['body'] = {
            'message': 'can\'t create cluster \'%s\'' % cluster_name
        }

        if not self.is_valid_name(cluster_name):
            raise CseServerError(f"Invalid cluster name \'{cluster_name}\'")
        self._connect_tenant()
        self._connect_sys_admin()
        self.cluster_name = cluster_name
        self.cluster_id = str(uuid.uuid4())
        self.op = OP_CREATE_CLUSTER
        self.update_task(
            TaskStatus.RUNNING,
            message='Creating cluster %s(%s)' % (cluster_name,
                                                 self.cluster_id))
        self.daemon = True
        self.start()
        response_body = {}
        response_body['name'] = self.cluster_name
        response_body['cluster_id'] = self.cluster_id
        response_body['task_href'] = self.task_resource.get('href')
        result['body'] = response_body
        result['status_code'] = ACCEPTED
        return result

    @rollback
    def create_cluster_thread(self):
        network_name = self.body['network']
        try:
            clusters = load_from_metadata(
                self.tenant_client, name=self.cluster_name)
            if len(clusters) != 0:
                raise ClusterAlreadyExistsError(f"Cluster {self.cluster_name} "
                                                "already exists.")
            org_resource = self.tenant_client.get_org()
            org = Org(self.tenant_client, resource=org_resource)
            vdc_resource = org.get_vdc(self.body['vdc'])
            vdc = VDC(self.tenant_client, resource=vdc_resource)
            template = self.get_template()
            self.update_task(
                TaskStatus.RUNNING,
                message='Creating cluster vApp %s(%s)' % (self.cluster_name,
                                                          self.cluster_id))
            try:
                vapp_resource = vdc.create_vapp(
                    self.cluster_name,
                    description='cluster %s' % self.cluster_name,
                    network=network_name,
                    fence_mode='bridged')
            except Exception as e:
                raise ClusterOperationError(
                    'Error while creating vApp:', str(e))

            self.tenant_client.get_task_monitor().wait_for_status(
                vapp_resource.Tasks.Task[0])
            tags = {}
            tags['cse.cluster.id'] = self.cluster_id
            tags['cse.version'] = pkg_resources.require(
                'container-service-extension')[0].version
            tags['cse.template'] = template['name']
            vapp = VApp(self.tenant_client, href=vapp_resource.get('href'))
            for k, v in tags.items():
                task = vapp.set_metadata('GENERAL', 'READWRITE', k, v)
                self.tenant_client.get_task_monitor().wait_for_status(task)
            self.update_task(
                TaskStatus.RUNNING,
                message='Creating master node for %s(%s)' % (self.cluster_name,
                                                             self.cluster_id))
            vapp.reload()

            server_config = get_server_runtime_config()
            try:
                add_nodes(1, template, TYPE_MASTER, server_config,
                          self.tenant_client, org, vdc, vapp, self.body)
            except Exception as e:
                raise MasterNodeCreationError(
                    "Error while adding master node:", str(e))

            self.update_task(
                TaskStatus.RUNNING,
                message='Initializing cluster %s(%s)' % (self.cluster_name,
                                                         self.cluster_id))
            vapp.reload()
            init_cluster(server_config, vapp, template)
            master_ip = get_master_ip(server_config, vapp, template)
            task = vapp.set_metadata('GENERAL', 'READWRITE', 'cse.master.ip',
                                     master_ip)
            self.tenant_client.get_task_monitor().wait_for_status(task)
            if self.body['node_count'] > 0:
                self.update_task(
                    TaskStatus.RUNNING,
                    message='Creating %s node(s) for %s(%s)' %
                    (self.body['node_count'], self.cluster_name,
                     self.cluster_id))
                try:
                    add_nodes(self.body['node_count'], template, TYPE_NODE,
                              server_config, self.tenant_client, org, vdc,
                              vapp, self.body)
                except Exception as e:
                    raise WorkerNodeCreationError(
                        "Error while creating worker node:", str(e))

                self.update_task(
                    TaskStatus.RUNNING,
                    message='Adding %s node(s) to %s(%s)' %
                    (self.body['node_count'], self.cluster_name,
                     self.cluster_id))
                vapp.reload()
                join_cluster(server_config, vapp, template)
            if self.body['enable_nfs']:
                self.update_task(
                    TaskStatus.RUNNING,
                    message='Creating NFS node for %s(%s)' %
                            (self.cluster_name,
                             self.cluster_id))
                try:
                    add_nodes(1, template, TYPE_NFS,
                              server_config, self.tenant_client, org, vdc,
                              vapp, self.body)
                except Exception as e:
                    raise NFSNodeCreationError(
                        "Error while creating NFS node:", str(e))

            self.update_task(
                TaskStatus.SUCCESS,
                message='Created cluster %s(%s)' % (self.cluster_name,
                                                    self.cluster_id))
        except (MasterNodeCreationError, WorkerNodeCreationError,
                NFSNodeCreationError, ClusterJoiningError,
                ClusterInitializationError, ClusterOperationError) as e:
            LOGGER.error(traceback.format_exc())
            error_obj = error_to_json(e)
            stack_trace = ''.join(error_obj[ERROR_MESSAGE][ERROR_STACKTRACE])
            self.update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE][ERROR_DESCRIPTION],
                stack_trace=stack_trace)
            raise e
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            error_obj = error_to_json(e)
            stack_trace = ''.join(error_obj[ERROR_MESSAGE][ERROR_STACKTRACE])
            self.update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE][ERROR_DESCRIPTION],
                stack_trace=stack_trace)
        finally:
            self._disconnect_sys_admin()

    @exception_handler
    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def delete_cluster(self):
        result = {}
        result['body'] = {}
        LOGGER.debug(f"About to delete cluster with name: {self.body['name']}")

        self.cluster_name = self.body['name']
        self._connect_tenant()
        self._connect_sys_admin()
        self.op = OP_DELETE_CLUSTER
        clusters = load_from_metadata(
            self.tenant_client, name=self.cluster_name)
        if len(clusters) != 1:
            raise CseServerError(f"Cluster {self.cluster_name} not found.")
        self.cluster = clusters[0]
        self.cluster_id = self.cluster['cluster_id']
        self.update_task(
            TaskStatus.RUNNING,
            message='Deleting cluster %s(%s)' % (self.cluster_name,
                                                 self.cluster_id))
        self.daemon = True
        self.start()
        response_body = {}
        response_body['cluster_name'] = self.cluster_name
        response_body['task_href'] = self.task_resource.get('href')
        result['body'] = response_body
        result['status_code'] = ACCEPTED
        return result

    def delete_cluster_thread(self):
        LOGGER.debug('About to delete cluster with name: %s',
                     self.cluster_name)
        try:
            vdc = VDC(self.tenant_client, href=self.cluster['vdc_href'])
            task = vdc.delete_vapp(self.cluster['name'], force=True)
            self.tenant_client.get_task_monitor().wait_for_status(task)
            self.update_task(
                TaskStatus.SUCCESS,
                message='Deleted cluster %s(%s)' % (self.cluster_name,
                                                    self.cluster_id))
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self.update_task(TaskStatus.ERROR, error_message=str(e))
        finally:
            self._disconnect_sys_admin()

    @exception_handler
    def get_cluster_config(self, cluster_name):
        result = {}
        self._connect_tenant()
        clusters = load_from_metadata(
            self.tenant_client, name=cluster_name)
        if len(clusters) != 1:
            raise CseServerError('Cluster \'%s\' not found' % cluster_name)
        vapp = VApp(self.tenant_client, href=clusters[0]['vapp_href'])
        template = self.get_template(name=clusters[0]['template'])
        server_config = get_server_runtime_config()
        result['body'] = get_cluster_config(server_config, vapp,
                                            template['admin_password'])
        result['status_code'] = OK
        return result

    @exception_handler
    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def create_nodes(self):
        result = {'body': {}}
        self.cluster_name = self.body['name']
        LOGGER.debug(f"About to add {self.body['node_count']} nodes to cluster"
                     " {self.cluster_name} on VDC {self.body['vdc']}, "
                     "sp={self.body['storage_profile']}")
        if self.body['node_count'] < 1:
            raise CseServerError(f"Invalid node count: "
                                 f"{self.body['node_count']}.")
        self._connect_tenant()
        self._connect_sys_admin()
        clusters = load_from_metadata(
            self.tenant_client, name=self.cluster_name)
        if len(clusters) != 1:
            raise CseServerError(
                'Cluster \'%s\' not found.' % self.cluster_name)
        self.cluster = clusters[0]
        self.op = OP_CREATE_NODES
        self.cluster_id = self.cluster['cluster_id']
        self.update_task(
            TaskStatus.RUNNING,
            message=f"Adding {self.body['node_count']} node(s) to cluster "
                    "{self.cluster_name}({self.cluster_id})")
        self.daemon = True
        self.start()
        response_body = {}
        response_body['cluster_name'] = self.cluster_name
        response_body['task_href'] = self.task_resource.get('href')
        result['body'] = response_body
        result['status_code'] = ACCEPTED
        return result

    @rollback
    def create_nodes_thread(self):
        LOGGER.debug('About to add nodes to cluster with name: %s',
                     self.cluster_name)
        try:
            server_config = get_server_runtime_config()
            org_resource = self.tenant_client.get_org()
            org = Org(self.tenant_client, resource=org_resource)
            vdc = VDC(self.tenant_client, href=self.cluster['vdc_href'])
            vapp = VApp(self.tenant_client, href=self.cluster['vapp_href'])
            template = self.get_template()
            self.update_task(
                TaskStatus.RUNNING,
                message='Creating %s node(s) for %s(%s)' %
                        (self.body['node_count'],
                         self.cluster_name,
                         self.cluster_id))
            new_nodes = add_nodes(self.body['node_count'], template,
                                  self.body['node_type'],
                                  server_config, self.tenant_client,
                                  org, vdc, vapp, self.body)
            if self.body['node_type'] == TYPE_NFS:
                self.update_task(
                    TaskStatus.SUCCESS,
                    message='Created %s node(s) for %s(%s)' %
                            (self.body['node_count'],
                             self.cluster_name,
                             self.cluster_id))
            elif self.body['node_type'] == TYPE_NODE:
                self.update_task(
                    TaskStatus.RUNNING,
                    message='Adding %s node(s) to %s(%s)' %
                            (self.body['node_count'],
                             self.cluster_name,
                             self.cluster_id))
                target_nodes = []
                for spec in new_nodes['specs']:
                    target_nodes.append(spec['target_vm_name'])
                vapp.reload()
                join_cluster(server_config, vapp, template, target_nodes)
                self.update_task(
                    TaskStatus.SUCCESS,
                    message='Added %s node(s) to cluster %s(%s)' %
                            (self.body['node_count'],
                             self.cluster_name,
                             self.cluster_id))
        except NodeCreationError as e:
            error_obj = error_to_json(e)
            LOGGER.error(traceback.format_exc())
            stack_trace = ''.join(error_obj[ERROR_MESSAGE][ERROR_STACKTRACE])
            self.update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE][ERROR_DESCRIPTION],
                stack_trace=stack_trace)
            raise
        except Exception as e:
            error_obj = error_to_json(e)
            LOGGER.error(traceback.format_exc())
            stack_trace = ''.join(error_obj[ERROR_MESSAGE][ERROR_STACKTRACE])
            self.update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE][ERROR_DESCRIPTION],
                stack_trace=stack_trace)
        finally:
            self._disconnect_sys_admin()

    @exception_handler
    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def delete_nodes(self):
        result = {'body': {}}
        self.cluster_name = self.body['name']
        LOGGER.debug(f"About to delete nodes from cluster with name: "
                     "{self.body['name']}")

        if len(self.body['nodes']) < 1:
            raise CseServerError(f"Invalid list of nodes: "
                                 f"{self.body['nodes']}.")
        for node in self.body['nodes']:
            if node.startswith(TYPE_MASTER):
                raise CseServerError(
                    'Can\'t delete a master node: \'%s\'.' % node)
        self._connect_tenant()
        self._connect_sys_admin()
        clusters = load_from_metadata(
            self.tenant_client, name=self.cluster_name)
        if len(clusters) != 1:
            raise CseServerError(
                'Cluster \'%s\' not found.' % self.cluster_name)
        self.cluster = clusters[0]
        self.op = OP_DELETE_NODES
        self.cluster_id = self.cluster['cluster_id']
        self.update_task(
            TaskStatus.RUNNING,
            message=f"Deleting {len(self.body['nodes'])} node(s) from cluster "
                    "{self.cluster_name}({self.cluster_id})")
        self.daemon = True
        self.start()
        response_body = {}
        response_body['cluster_name'] = self.cluster_name
        response_body['task_href'] = self.task_resource.get('href')
        result['body'] = response_body
        result['status_code'] = ACCEPTED
        return result

    def delete_nodes_thread(self):
        LOGGER.debug('About to delete nodes from cluster with name: %s',
                     self.cluster_name)
        try:
            vapp = VApp(self.tenant_client, href=self.cluster['vapp_href'])
            template = self.get_template()
            self.update_task(
                TaskStatus.RUNNING,
                message='Deleting %s node(s) from %s(%s)' %
                (len(self.body['nodes']), self.cluster_name, self.cluster_id))
            try:
                server_config = get_server_runtime_config()
                delete_nodes_from_cluster(server_config,
                                          vapp,
                                          template,
                                          self.body['nodes'],
                                          self.body['force'])
            except Exception:
                LOGGER.error(f"Couldn't delete node {self.body['nodes']} from "
                             "cluster:{self.cluster_name}")
            self.update_task(
                TaskStatus.RUNNING,
                message='Undeploying %s node(s) for %s(%s)' %
                (len(self.body['nodes']), self.cluster_name, self.cluster_id))
            for vm_name in self.body['nodes']:
                vm = VM(self.tenant_client, resource=vapp.get_vm(vm_name))
                try:
                    task = vm.undeploy()
                    self.tenant_client.get_task_monitor().wait_for_status(task)
                except Exception:
                    LOGGER.warning('couldn\'t undeploy VM %s' % vm_name)
            self.update_task(
                TaskStatus.RUNNING,
                message='Deleting %s VM(s) for %s(%s)' %
                (len(self.body['nodes']), self.cluster_name, self.cluster_id))
            task = vapp.delete_vms(self.body['nodes'])
            self.tenant_client.get_task_monitor().wait_for_status(task)
            self.update_task(
                TaskStatus.SUCCESS,
                message='Deleted %s node(s) to cluster %s(%s)' %
                (len(self.body['nodes']), self.cluster_name, self.cluster_id))
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            error_obj = error_to_json(e)
            stack_trace = ''.join(error_obj[ERROR_MESSAGE][ERROR_STACKTRACE])
            self.update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE][ERROR_DESCRIPTION],
                stack_trace=stack_trace)
        finally:
            self._disconnect_sys_admin()

    @exception_handler
    def enable_ovdc_for_kubernetes(self):
        """Enable ovdc for k8-cluster deployment on given container provider.

        :return: result object

        :rtype: dict

        :raises CseServerError: if the user is not system administrator.
        """
        result = dict()
        self._connect_tenant()
        if self.tenant_client.is_sysadmin():
            ovdc_cache = OvdcCache(self.tenant_client)
            task = ovdc_cache.set_ovdc_container_provider_metadata(
                self.body['ovdc_name'],
                ovdc_id=self.body.get('ovdc_id', None),
                container_provider=self.body.get('container_provider', None),
                pks_plans=self.body['pks_plans'],
                org_name=self.body.get('org_name', None))
            response_body = dict()
            response_body['ovdc_name'] = self.body['ovdc_name']
            response_body['task_href'] = task.get('href')
            result['body'] = response_body
            result['status_code'] = ACCEPTED
            return result
        else:
            raise CseServerError("Unauthorized Operation")

    @exception_handler
    def ovdc_info_for_kubernetes(self):
        """Info on ovdc for k8s deployment on the given container provider.

        :return: result object

        :rtype: dict

        :raises CseServerError: if the user is not system administrator.
        """
        result = dict()
        self._connect_tenant()
        if self.tenant_client.is_sysadmin():
            ovdc_cache = OvdcCache(self.tenant_client)
            metadata = ovdc_cache.get_ovdc_container_provider_metadata(
                self.body.get('ovdc_name', None),
                ovdc_id=self.body.get('ovdc_id', None),
                org_name=self.body.get('org_name', None))
            # remove username, secret from sending to client
            metadata.pop('username', None)
            metadata.pop('secret', None)
            result = dict()
            result['status_code'] = OK
            result['body'] = metadata
            return result
        else:
            raise CseServerError("Unauthorized Operation")

    def node_rollback(self, node_list):
        """Rollback for node creation failure.

        :param list node_list: faulty nodes to be deleted
        """
        LOGGER.info(f"About to rollback nodes from cluster with name: "
                    "{self.cluster_name}")
        LOGGER.info(f"Node list to be deleted:{node_list}")
        vapp = VApp(self.tenant_client, href=self.cluster['vapp_href'])
        template = self.get_template()
        try:
            server_config = get_server_runtime_config()
            delete_nodes_from_cluster(server_config, vapp, template,
                                      node_list, force=True)
        except Exception:
            LOGGER.warning("Couldn't delete node {node_list} from cluster:"
                           "{self.cluster_name}")
        for vm_name in node_list:
            vm = VM(self.tenant_client, resource=vapp.get_vm(vm_name))
            try:
                vm.undeploy()
            except Exception:
                LOGGER.warning(f"Couldn't undeploy VM {vm_name}")
        vapp.delete_vms(node_list)
        LOGGER.info(f"Successfully deleted nodes: {node_list}")

    def cluster_rollback(self):
        """Rollback for cluster creation failure."""
        LOGGER.info(f"About to rollback cluster with name: "
                    "{self.cluster_name}")
        self._connect_tenant()
        clusters = load_from_metadata(
            self.tenant_client, name=self.cluster_name)
        if len(clusters) != 1:
            LOGGER.debug('Cluster %s not found.' % self.cluster_name)
            return
        self.cluster = clusters[0]
        vdc = VDC(self.tenant_client, href=self.cluster['vdc_href'])
        vdc.delete_vapp(self.cluster['name'], force=True)
        LOGGER.info(f"Successfully deleted cluster: {self.cluster_name}")
