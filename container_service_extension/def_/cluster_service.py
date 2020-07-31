# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import copy
import random
import re
import string
import threading
import time
from typing import List

import pkg_resources
import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.task as vcd_task
import pyvcloud.vcd.vapp as vcd_vapp
from pyvcloud.vcd.vdc import VDC
import pyvcloud.vcd.vm as vcd_vm
import semantic_version as semver

import container_service_extension.abstract_broker as abstract_broker
import container_service_extension.compute_policy_manager as compute_policy_manager  # noqa: E501
import container_service_extension.def_.entity_service as def_entity_svc
import container_service_extension.def_.models as def_models
import container_service_extension.def_.utils as def_utils
import container_service_extension.exceptions as e
import container_service_extension.local_template_manager as ltm
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.operation_context as ctx
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import ClusterMetadataKey
from container_service_extension.server_constants import CSE_CLUSTER_KUBECONFIG_PATH # noqa: E501
from container_service_extension.server_constants import KwargKey
from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.server_constants import NodeType
from container_service_extension.server_constants import ScriptFile
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.shared_constants import DefEntityOperation
from container_service_extension.shared_constants import DefEntityOperationStatus  # noqa: E501
from container_service_extension.shared_constants import DefEntityPhase
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_details
import container_service_extension.utils as utils
import container_service_extension.vsphere_utils as vs_utils


class ClusterService(abstract_broker.AbstractBroker):
    """Handles cluster operations for native DEF based clusters."""

    def __init__(self, op_ctx: ctx.OperationContext):
        # TODO(DEF) Once all the methods are modified to use defined entities,
        #  the param OperationContext needs to be replaced by cloudapiclient.
        self.context: ctx.OperationContext = None
        # populates above attributes
        super().__init__(op_ctx)

        self.task = None
        self.task_resource = None
        self.task_update_lock = threading.Lock()
        self.entity_svc = def_entity_svc.DefEntityService(
            op_ctx.cloudapi_client)

    def get_cluster_info(self, cluster_id: str) -> def_models.DefEntity:
        """Get the corresponding defined entity of the native cluster.

        This method ensures to return the latest state of the cluster vApp.
        It syncs the defined entity with the state of the cluster vApp before
        returning the defined entity.
        """
        return self._sync_def_entity(cluster_id)

    def list_clusters(self, filters: dict) -> List[def_models.DefEntity]:
        """List corresponding defined entities of all native clusters."""
        ent_type: def_models.DefEntityType = def_utils.get_registered_def_entity_type()  # noqa: E501
        return self.entity_svc.list_entities_by_entity_type(
            vendor=ent_type.vendor,
            nss=ent_type.nss,
            version=ent_type.version,
            filters=filters)

    def get_cluster_config(self, cluster_id: str):
        """Get the cluster's kube config contents.

        :param str cluster_id:
        :return: Dictionary containing cluster config.
        :rtype: dict
        """
        curr_entity = self.entity_svc.get_entity(cluster_id)

        # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
        #  based clusters

        vapp = vcd_vapp.VApp(self.context.client, href=curr_entity.externalId)
        master_node_name = curr_entity.entity.status.nodes.master.name

        LOGGER.debug(f"getting file from node {master_node_name}")
        password = vapp.get_admin_password(master_node_name)
        vs = vs_utils.get_vsphere(self.context.sysadmin_client, vapp,
                                  vm_name=master_node_name, logger=LOGGER)
        vs.connect()
        moid = vapp.get_vm_moid(master_node_name)
        vm = vs.get_vm_by_moid(moid)
        result = vs.download_file_from_guest(vm, 'root', password,
                                             CSE_CLUSTER_KUBECONFIG_PATH)

        if not result:
            raise e.ClusterOperationError("Couldn't get cluster configuration")

        return result.content.decode()

    def get_cluster_upgrade_plan(self, cluster_id: str):
        """Get the template names/revisions that the cluster can upgrade to.

        :param str cluster_id:
        :return: A list of dictionaries with keys defined in LocalTemplateKey

        :rtype: List[Dict]
        """
        curr_entity = self.entity_svc.get_entity(cluster_id)

        # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
        #  based clusters
        # cse_params = copy.deepcopy(validated_data)
        # cse_params[PayloadKey.CLUSTER_ID] = cluster[PayloadKey.CLUSTER_ID]
        # record_user_action_details(cse_operation=CseOperation.CLUSTER_UPGRADE_PLAN, cse_params=cse_params)  # noqa: E501

        return self._get_cluster_upgrade_plan(curr_entity.entity.spec.k8_distribution.template_name, # noqa: E501
                                              curr_entity.entity.spec.k8_distribution.template_revision) # noqa: E501

    def _get_cluster_upgrade_plan(self, source_template_name,
                                  source_template_revision) -> List[dict]: # noqa: E501
        """Get list of templates that a given cluster can upgrade to.

        :param str source_template_name:
        :param str source_template_revision:
        :return: List of dictionary containing templates
        :rtype: List[dict]
        """
        upgrades = []
        config = utils.get_server_runtime_config()
        for t in config['broker']['templates']:
            if source_template_name in t[LocalTemplateKey.UPGRADE_FROM]:
                if t[LocalTemplateKey.NAME] == source_template_name and \
                        int(t[LocalTemplateKey.REVISION]) <= int(source_template_revision): # noqa: E501
                    continue
                upgrades.append(t)

        return upgrades

    def create_cluster(self, cluster_spec: def_models.ClusterEntity):
        """Start the cluster creation operation.

        Creates corresponding defined entity in vCD for every native cluster.
        Updates the defined entity with new properties after the cluster
        creation.

        **telemetry: Optional

        :return: Defined entity of the cluster
        :rtype: def_models.DefEntity
        """
        cluster_name = cluster_spec.metadata.cluster_name
        org_name = cluster_spec.metadata.org_name
        ovdc_name = cluster_spec.metadata.ovdc_name
        template_name = cluster_spec.spec.k8_distribution.template_name
        template_revision = cluster_spec.spec.k8_distribution.template_revision

        # check that cluster name is syntactically valid
        if not is_valid_cluster_name(cluster_name):
            raise e.CseServerError(f"Invalid cluster name '{cluster_name}'")

        # Check that cluster name doesn't already exist.
        # Do not replace the below with the check to verify if defined entity
        # already exists. It will not give accurate result as even sys-admin
        # cannot view all the defined entities unless native entity type admin
        # view right is assigned.
        try:
            get_cluster(self.context.client, cluster_name,
                        org_name=org_name,
                        ovdc_name=ovdc_name)
            raise e.ClusterAlreadyExistsError(
                f"Cluster '{cluster_name}' already exists.")
        except e.ClusterNotFoundError:
            pass

        # check that requested/default template is valid
        template = get_template(name=template_name, revision=template_revision)

        # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
        #  based clusters

        # create the corresponding defined entity .
        def_entity = def_models.DefEntity(entity=cluster_spec)
        msg = f"Creating cluster vApp '{cluster_name}' ({def_entity.id}) " \
              f"from template '{template_name}' (revision {template_revision})"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        def_entity.entity.status.task_href = self.task_resource.get('href')
        def_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.CREATE,
                           DefEntityOperationStatus.IN_PROGRESS))
        def_entity.entity.status.kubernetes = \
            _create_k8s_software_string(template[LocalTemplateKey.KUBERNETES],
                                        template[LocalTemplateKey.KUBERNETES_VERSION]) # noqa: E501
        def_entity.entity.status.cni = \
            _create_k8s_software_string(template[LocalTemplateKey.CNI],
                                        template[LocalTemplateKey.CNI_VERSION])
        def_entity.entity.status.docker_version = template[LocalTemplateKey.DOCKER_VERSION] # noqa: E501
        def_entity.entity.status.os = template[LocalTemplateKey.OS]
        self.entity_svc. \
            create_entity(def_utils.get_registered_def_entity_type().id,
                          entity=def_entity)
        self.context.is_async = True
        def_entity = self.entity_svc.get_native_entity_by_name(cluster_name)
        self._create_cluster_async(def_entity.id, cluster_spec)
        return def_entity

    @utils.run_async
    def _create_cluster_async(self, cluster_id: str,
                              cluster_spec: def_models.ClusterEntity):
        try:
            cluster_name = cluster_spec.metadata.cluster_name
            org_name = cluster_spec.metadata.org_name
            ovdc_name = cluster_spec.metadata.ovdc_name
            num_workers = cluster_spec.spec.workers.count
            master_sizing_class = cluster_spec.spec.control_plane.sizing_class
            worker_sizing_class = cluster_spec.spec.workers.sizing_class
            master_storage_profile = cluster_spec.spec.control_plane.storage_profile  # noqa: E501
            worker_storage_profile = cluster_spec.spec.workers.storage_profile  # noqa: E501
            nfs_count = cluster_spec.spec.nfs.count
            nfs_sizing_class = cluster_spec.spec.nfs.sizing_class
            nfs_storage_profile = cluster_spec.spec.nfs.storage_profile
            network_name = cluster_spec.spec.settings.network
            template_name = cluster_spec.spec.k8_distribution.template_name
            template_revision = cluster_spec.spec.k8_distribution.template_revision  # noqa: E501
            ssh_key = cluster_spec.spec.settings.ssh_key
            rollback = cluster_spec.spec.settings.rollback_on_failure

            vapp = None
            org = vcd_utils.get_org(self.context.client, org_name=org_name)
            vdc = vcd_utils.get_vdc(self.context.client,
                                    vdc_name=ovdc_name,
                                    org=org)

            LOGGER.debug(f"About to create cluster '{cluster_name}' on "
                         f"{ovdc_name} with {num_workers} worker nodes, "
                         f"storage profile={worker_storage_profile}")
            msg = f"Creating cluster vApp {cluster_name} ({cluster_id})"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            try:
                vapp_resource = vdc.create_vapp(
                    cluster_name,
                    description=f"cluster '{cluster_name}'",
                    network=network_name,
                    fence_mode='bridged')
            except Exception as err:
                msg = f"Error while creating vApp: {err}"
                LOGGER.debug(str(err))
                raise e.ClusterOperationError(msg)
            self.context.client.get_task_monitor().wait_for_status(vapp_resource.Tasks.Task[0]) # noqa: E501

            template = get_template(template_name, template_revision)

            tags = {
                ClusterMetadataKey.CLUSTER_ID: cluster_id,
                ClusterMetadataKey.CSE_VERSION: pkg_resources.require('container-service-extension')[0].version, # noqa: E501
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME], # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION], # noqa: E501
                ClusterMetadataKey.OS: template[LocalTemplateKey.OS], # noqa: E501
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION], # noqa: E501
                ClusterMetadataKey.KUBERNETES: template[LocalTemplateKey.KUBERNETES], # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION], # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION] # noqa: E501
            }
            vapp = vcd_vapp.VApp(self.context.client,
                                 href=vapp_resource.get('href'))
            task = vapp.set_multiple_metadata(tags)
            self.context.client.get_task_monitor().wait_for_status(task)

            msg = f"Creating master node for cluster '{cluster_name}' " \
                  f"({cluster_id})"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            vapp.reload()
            server_config = utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            try:
                add_nodes(self.context.sysadmin_client,
                          num_nodes=1,
                          node_type=NodeType.MASTER,
                          org=org,
                          vdc=vdc,
                          vapp=vapp,
                          catalog_name=catalog_name,
                          template=template,
                          network_name=network_name,
                          storage_profile=master_storage_profile,
                          ssh_key=ssh_key,
                          sizing_class_name=master_sizing_class)
            except Exception as err:
                raise e.MasterNodeCreationError("Error adding master node:",
                                                str(err))

            msg = f"Initializing cluster '{cluster_name}' ({cluster_id})"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            vapp.reload()
            init_cluster(self.context.sysadmin_client,
                         vapp,
                         template[LocalTemplateKey.NAME],
                         template[LocalTemplateKey.REVISION])
            master_ip = get_master_ip(self.context.sysadmin_client, vapp)
            task = vapp.set_metadata('GENERAL', 'READWRITE', 'cse.master.ip',
                                     master_ip)
            self.context.client.get_task_monitor().wait_for_status(task)

            msg = f"Creating {num_workers} node(s) for cluster " \
                  f"'{cluster_name}' ({cluster_id})"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            try:
                add_nodes(self.context.sysadmin_client,
                          num_nodes=num_workers,
                          node_type=NodeType.WORKER,
                          org=org,
                          vdc=vdc,
                          vapp=vapp,
                          catalog_name=catalog_name,
                          template=template,
                          network_name=network_name,
                          storage_profile=worker_storage_profile,
                          ssh_key=ssh_key,
                          sizing_class_name=worker_sizing_class)
            except Exception as err:
                raise e.WorkerNodeCreationError("Error creating worker node:",
                                                str(err))

            msg = f"Adding {num_workers} node(s) to cluster " \
                  f"'{cluster_name}' ({cluster_id})"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            vapp.reload()
            join_cluster(self.context.sysadmin_client,
                         vapp,
                         template[LocalTemplateKey.NAME],
                         template[LocalTemplateKey.REVISION])

            if nfs_count > 0:
                msg = f"Creating {nfs_count} NFS nodes for cluster " \
                      f"'{cluster_name}' ({cluster_id})"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                try:
                    add_nodes(self.context.sysadmin_client,
                              num_nodes=nfs_count,
                              node_type=NodeType.NFS,
                              org=org,
                              vdc=vdc,
                              vapp=vapp,
                              catalog_name=catalog_name,
                              template=template,
                              network_name=network_name,
                              storage_profile=nfs_storage_profile,
                              ssh_key=ssh_key,
                              sizing_class_name=nfs_sizing_class)
                except Exception as err:
                    raise e.NFSNodeCreationError("Error creating NFS node:",
                                                 str(err))

            msg = f"Created cluster '{cluster_name}' ({cluster_id})"
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)

            # Update defined entity instance with new properties like vapp_id,
            # master_ip and nodes.
            # TODO(DEF) VCDA-1567 Schema doesn't yet have nodes definition.
            #  master and worker "nodes" also have to be updated.
            def_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
            def_entity.externalId = vapp_resource.get('href')
            def_entity.entity.status.master_ip = master_ip
            def_entity.entity.status.phase = str(
                DefEntityPhase(DefEntityOperation.CREATE,
                               DefEntityOperationStatus.SUCCEEDED))
            def_entity.entity.status.nodes = self._get_nodes_details(vapp)

            self.entity_svc.update_entity(cluster_id, def_entity)
            self.entity_svc.resolve_entity(cluster_id)
        except (e.MasterNodeCreationError, e.WorkerNodeCreationError,
                e.NFSNodeCreationError, e.ClusterJoiningError,
                e.ClusterInitializationError, e.ClusterOperationError) as err:
            if rollback:
                msg = f"Error creating cluster '{cluster_name}'. " \
                      f"Deleting cluster (rollback=True)"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    _delete_vapp(self.context.client,
                                 self._get_vdc_href(org_name, ovdc_name),
                                 cluster_name)
                    # Delete the corresponding defined entity
                    self.entity_svc.delete_entity(cluster_id)
                except Exception:
                    LOGGER.error(f"Failed to delete cluster '{cluster_name}'",
                                 exc_info=True)
            LOGGER.error(f"Error creating cluster '{cluster_name}'",
                         exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              error_message=str(err))
            self._fail_operation_and_resolve_entity(cluster_id,
                                                    DefEntityOperation.CREATE,
                                                    vapp)
            # raising an exception here prints a stacktrace to server console
        except Exception as err:
            self._fail_operation_and_resolve_entity(cluster_id,
                                                    DefEntityOperation.CREATE,
                                                    vapp)
            LOGGER.error(f"Unknown error creating cluster '{cluster_name}'",
                         exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              error_message=str(err))
        finally:
            self.context.end()

    def _get_nodes_details(self, vapp):
        """Get the details of the nodes given a vapp.

        This method should not raise an exception. It is being used in the
        exception blocks to sync the defined entity status of any given cluster
        It returns None in the case of any unexpected errors.

        :param vapp: vApp
        :return: Node details
        :rtype: container_service_extension.def_.models.Nodes
        """
        try:
            vms = vapp.get_all_vms()
            workers = []
            nfs_nodes = []
            for vm in vms:
                # skip processing vms in 'unresolved' state.
                if int(vm.get('status')) == 0:
                    continue
                name = vm.get('name')
                ip = None
                try:
                    ip = vapp.get_primary_ip(name)
                except Exception:
                    LOGGER.error(f"Failed to retrieve the IP of the node "
                                 f"{name} in cluster {vapp.name}",
                                 exc_info=True)
                sizing_class = None
                if hasattr(vm, 'ComputePolicy') and hasattr(vm.ComputePolicy,
                                                            'VmSizingPolicy'):
                    policy_name = vm.ComputePolicy.VmSizingPolicy.get('name')
                    sizing_class = compute_policy_manager.\
                        ComputePolicyManager.get_policy_display_name(policy_name)  # noqa: E501
                if name.startswith(NodeType.MASTER):
                    master = def_models.Node(name=name, ip=ip,
                                             sizing_class=sizing_class)
                elif name.startswith(NodeType.WORKER):
                    workers.append(
                        def_models.Node(name=name, ip=ip,
                                        sizing_class=sizing_class))
                elif name.startswith(NodeType.NFS):
                    exports = None
                    try:
                        exports = get_nfs_exports(self.context.sysadmin_client,
                                                  ip,
                                                  vapp, name)
                    except Exception:
                        LOGGER.error(f"Failed to retrieve the NFS exports of "
                                     f"node {name} of cluster {vapp.name} ",
                                     exc_info=True)
                    nfs_nodes.append(def_models.NfsNode(name=name, ip=ip,
                                                        sizing_class=sizing_class,  # noqa: E501
                                                        exports=exports))
            return def_models.Nodes(master=master, workers=workers,
                                    nfs=nfs_nodes)
        except Exception as e:
            LOGGER.error(
                f"Failed to retrieve the status of the nodes of the cluster {vapp.name}: {e}")  # noqa: E501

    def _fail_operation_and_resolve_entity(self, cluster_id: str,
                                           op: DefEntityOperation,
                                           vapp=None):
        # get the current state of the defined entity
        def_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501

        # sync the defined entity with the latest status of cluster vApp and
        # fail the operation.
        def_entity.entity.status.phase = \
            str(DefEntityPhase(op, DefEntityOperationStatus.FAILED))
        self._sync_def_entity(cluster_id, def_entity)
        self.entity_svc.resolve_entity(cluster_id)

    def resize_cluster(self, cluster_id: str,
                       cluster_spec: def_models.ClusterEntity):
        """Start the resize cluster operation.

        :param str cluster_id: Defined entity Id of the cluster
        :param DefEntity cluster_spec: Input cluster spec
        :return: DefEntity of the cluster with the updated operation status
        and task_href.

        :rtype: DefEntity
        """
        # Get the existing defined entity for the given cluster id
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
        cluster_name: str = curr_entity.name
        curr_worker_count: int = curr_entity.entity.spec.workers.count
        curr_nfs_count: int = curr_entity.entity.spec.nfs.count
        state: str = curr_entity.state
        phase: DefEntityPhase = DefEntityPhase.from_phase(
            curr_entity.entity.status.phase)

        # compute the values of workers and nfs to be added or removed by
        # comparing the desired and the current state. "num_workers_to_add"
        # can hold either +ve or -ve value.
        desired_worker_count: int = cluster_spec.spec.workers.count
        desired_nfs_count: int = cluster_spec.spec.nfs.count
        num_workers_to_add: int = desired_worker_count - curr_worker_count
        num_nfs_to_add: int = desired_nfs_count - curr_nfs_count

        # check if cluster is in a valid state
        if state != def_utils.DEF_RESOLVED_STATE or phase.is_entity_busy():
            raise e.CseServerError(
                f"Cluster {cluster_name} with id {cluster_id} is not in a "
                f"valid state to be resized. Please contact the administrator")

        # Check if the desired worker and nfs count is valid
        if num_workers_to_add == 0 and num_nfs_to_add == 0:
            raise e.CseServerError(f"Cluster '{cluster_name}' already has "
                                   f"{desired_worker_count} workers and "
                                   f"{desired_nfs_count} nfs nodes.")
        elif desired_worker_count < 0:
            raise e.CseServerError(
                f"Worker count must be >= 0 (received {desired_worker_count})")
        elif num_nfs_to_add < 0:
            raise e.CseServerError("Scaling down nfs nodes is not supported")

        # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
        #  based clusters

        # update the task and defined entity.
        msg = f"Resizing the cluster '{cluster_name}' ({cluster_id}) to the " \
              f"desired worker count {desired_worker_count} and " \
              f"nfs count {desired_nfs_count}"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        curr_entity.entity.status.task_href = self.task_resource.get('href')
        curr_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.UPDATE,
                           DefEntityOperationStatus.IN_PROGRESS))
        curr_entity = self.entity_svc.update_entity(cluster_id, curr_entity)

        # trigger async operation
        self.context.is_async = True
        self._monitor_resize(cluster_id=cluster_id,
                             cluster_spec=cluster_spec)
        return curr_entity

    @utils.run_async
    def _monitor_resize(self, cluster_id, cluster_spec):
        """Triggers and monitors one or more async threads of resize.

        This method (or) thread triggers two async threads (for node
        addition and deletion) in parallel. It waits for both the threads to
        join before calling the resize operation complete.

        Performs below once child threads join back.
        - updates the defined entity
        - updates the task status to SUCCESS
        - ends the client context
        """
        try:
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
                cluster_id)
            cluster_name: str = curr_entity.name
            curr_worker_count: int = curr_entity.entity.spec.workers.count
            curr_nfs_count: int = curr_entity.entity.spec.nfs.count
            template_name = curr_entity.entity.spec.k8_distribution.template_name  # noqa: E501
            template_revision = curr_entity.entity.spec.k8_distribution.template_revision  # noqa: E501

            desired_worker_count: int = cluster_spec.spec.workers.count
            desired_nfs_count: int = cluster_spec.spec.nfs.count
            num_workers_to_add: int = desired_worker_count - curr_worker_count
            num_nfs_to_add: int = desired_nfs_count - curr_nfs_count

            if num_workers_to_add > 0 or num_nfs_to_add > 0:
                get_template(name=template_name, revision=template_revision)
                self._create_nodes_async(cluster_id=cluster_id,
                                         cluster_spec=cluster_spec)

                # TODO Below is the temporary fix to avoid parallel Recompose
                #  error between node creation and deletion threads. Below
                #  serializes the sequence of node creation and deletion.
                #  Remove the below block once the issue is fixed in pyvcloud.
                create_nodes_async_thread_name = utils.generate_thread_name(
                    self._create_nodes_async.__name__)
                for t in threading.enumerate():
                    if t.getName() == create_nodes_async_thread_name:
                        t.join()
            if num_workers_to_add < 0:
                self._delete_nodes_async(cluster_id=cluster_id,
                                         cluster_spec=cluster_spec)

            # Wait for the children threads of the current thread to join
            curr_thread_id = str(threading.current_thread().ident)
            for t in threading.enumerate():
                if t.getName().endswith(curr_thread_id):
                    t.join()

            # update the defined entity and the task status. Check if one of
            # the child threads had set the status to ERROR.
            curr_task_status = self.task_resource.get('status')
            if curr_task_status == vcd_client.TaskStatus.ERROR.value:
                curr_entity.entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.FAILED))
            else:
                msg = f"Resized the cluster '{cluster_name}' ({cluster_id}) " \
                      f"to the desired worker count {desired_worker_count} " \
                      f"and nfs count {desired_nfs_count}"
                self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
                curr_entity.entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.SUCCEEDED))

            self._sync_def_entity(cluster_id, curr_entity)
        except Exception as err:
            self._fail_operation_and_resolve_entity(cluster_id,
                                                    DefEntityOperation.UPDATE)
            LOGGER.error(f"Unexpected error while resizing nodes for "
                         f"{cluster_name} ({cluster_id}): {err}",
                         exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              error_message=str(err))
        finally:
            self.context.end()

    def _sync_def_entity(self, cluster_id, curr_entity=None, vapp=None):
        """Sync the defined entity with the latest vApp status."""
        if not curr_entity:
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
                cluster_id)
        if not vapp:
            vapp = vcd_vapp.VApp(self.context.client, href=curr_entity.externalId)  # noqa: E501
        curr_nodes_status = self._get_nodes_details(vapp)
        if curr_nodes_status:
            curr_entity.entity.spec.workers.count = len(
                curr_nodes_status.workers)
            curr_entity.entity.spec.nfs.count = len(curr_nodes_status.nfs)
            curr_entity.entity.status.nodes = curr_nodes_status
        return self.entity_svc.update_entity(cluster_id, curr_entity)

    def delete_cluster(self, cluster_id):
        """Start the delete cluster operation."""
        # Get the current state of the defined entity
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
            cluster_id)
        cluster_name: str = curr_entity.name
        org_name: str = curr_entity.entity.metadata.org_name
        ovdc_name: str = curr_entity.entity.metadata.ovdc_name
        phase: DefEntityPhase = DefEntityPhase.from_phase(
            curr_entity.entity.status.phase)

        # Check if cluster is busy
        if phase.is_entity_busy():
            raise e.CseServerError(
                f"Cluster {cluster_name} with id {cluster_id} is not in a "
                f"valid state to be deleted. Please contact administrator.")

        # TODO(DEF) Handle Telemetry

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        msg = f"Deleting cluster '{cluster_name}' ({cluster_id})"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

        curr_entity.entity.status.task_href = self.task_resource.get('href')
        curr_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.DELETE,
                           DefEntityOperationStatus.IN_PROGRESS))

        # attempt deleting the defined entity; lets vCD authorize the user
        # for delete operation. If deletion of the cluster fails for any
        # reason, defined entity will be recreated by async thread.
        self.entity_svc.delete_entity(cluster_id)
        self.context.is_async = True
        self._delete_cluster_async(cluster_name=cluster_name,
                                   org_name=org_name, ovdc_name=ovdc_name,
                                   def_entity=curr_entity)
        return curr_entity

    def _get_vdc_href(self, org_name, ovdc_name):
        client = self.context.client
        org = vcd_org.Org(client=client,
                          resource=client.get_org_by_name(org_name))
        vdc_resource = org.get_vdc(name=ovdc_name)
        return vdc_resource.get('href')

    def upgrade_cluster(self, cluster_id: str,
                        upgrade_spec: def_models.ClusterEntity):
        """Start the upgrade cluster operation.

        Upgrading cluster is an asynchronous task, so the returned
        `result['task_href']` can be polled to get updates on task progress.

        :param str cluster_id: id of the cluster to be upgraded
        :param def_models.ClusterEntity upgrade_spec: cluster spec with new
            kubernetes distribution and revision

        :return: Defined entity with upgrade in progress set
        :rtype: def_models.DefEntity representing the cluster
        """
        curr_entity = self.entity_svc.get_entity(cluster_id)
        cluster_name = curr_entity.entity.metadata.cluster_name
        new_template_name = upgrade_spec.spec.k8_distribution.template_name
        new_template_revision = upgrade_spec.spec.k8_distribution.template_revision # noqa: E501

        # check if cluster is in a valid state
        phase: DefEntityPhase = DefEntityPhase.from_phase(
            curr_entity.entity.status.phase)
        state: str = curr_entity.state
        if state != def_utils.DEF_RESOLVED_STATE or phase.is_entity_busy():
            raise e.CseServerError(
                f"Cluster {cluster_name} with id {cluster_id} is not in a "
                f"valid state to be upgraded. Please contact administrator.")

        # check that the specified template is a valid upgrade target
        template = {}
        valid_templates = self._get_cluster_upgrade_plan(curr_entity.entity.spec.k8_distribution.template_name, # noqa: E501
                                                         curr_entity.entity.spec.k8_distribution.template_revision) # noqa: E501

        for t in valid_templates:
            if t[LocalTemplateKey.NAME] == new_template_name and \
                    t[LocalTemplateKey.REVISION] == str(new_template_revision): # noqa: E501
                template = t
                break
        if not template:
            # TODO all of these e.CseServerError instances related to request
            # should be changed to BadRequestError (400)
            raise e.CseServerError(
                f"Specified template/revision ({new_template_name} revision "
                f"{new_template_revision}) is not a valid upgrade target for "
                f"cluster '{cluster_name}'.")

        # get cluster data (including node names) to pass to async function

        # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
        #  based clusters

        msg = f"Upgrading cluster '{cluster_name}' " \
              f"software to match template {new_template_name} (revision " \
              f"{new_template_revision}): Kubernetes: " \
              f"{curr_entity.entity.status.kubernetes} -> " \
              f"{template[LocalTemplateKey.KUBERNETES_VERSION]}, Docker-CE: " \
              f"{curr_entity.entity.status.docker_version} -> " \
              f"{template[LocalTemplateKey.DOCKER_VERSION]}, CNI: " \
              f"{curr_entity.entity.status.cni} -> " \
              f"{template[LocalTemplateKey.CNI_VERSION]}"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        LOGGER.info(f"{msg} ({curr_entity.externalId})")

        curr_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.UPGRADE, DefEntityOperationStatus.IN_PROGRESS)) # noqa: E501
        curr_entity.entity.status.task_href = self.task_resource.get('href')
        curr_entity = self.entity_svc.update_entity(cluster_id, curr_entity)

        self.context.is_async = True
        self._upgrade_cluster_async(cluster_id=cluster_id,
                                    template=template)
        return curr_entity

    def get_node_info(self, **kwargs):
        """Get node metadata as dictionary.

        **data: Required
            Required data: cluster_name, node_name
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional
        """
        raise NotImplementedError
        data = kwargs[KwargKey.DATA]
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.NODE_NAME
        ]
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        node_name = validated_data[RequestKey.NODE_NAME]

        cluster = get_cluster(self.context.client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the telemetry data
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster[PayloadKey.CLUSTER_ID]
            record_user_action_details(cse_operation=CseOperation.NODE_INFO, cse_params=cse_params)  # noqa: E501

        vapp = vcd_vapp.VApp(self.context.client, href=cluster['vapp_href'])
        vms = vapp.get_all_vms()
        node_info = None
        for vm in vms:
            vm_name = vm.get('name')
            if node_name != vm_name:
                continue

            node_info = {
                'name': vm_name,
                'numberOfCpus': '',
                'memoryMB': '',
                'status': vcd_client.VCLOUD_STATUS_MAP.get(int(vm.get('status'))), # noqa: E501
                'ipAddress': ''
            }
            if hasattr(vm, 'VmSpecSection'):
                node_info['numberOfCpus'] = vm.VmSpecSection.NumCpus.text
                node_info['memoryMB'] = vm.VmSpecSection.MemoryResourceMb.Configured.text # noqa: E501
            try:
                node_info['ipAddress'] = vapp.get_primary_ip(vm_name)
            except Exception:
                LOGGER.debug(f"Unable to get ip address of node {vm_name}")
            if vm_name.startswith(NodeType.MASTER):
                node_info['node_type'] = 'master'
            elif vm_name.startswith(NodeType.WORKER):
                node_info['node_type'] = 'worker'
            elif vm_name.startswith(NodeType.NFS):
                node_info['node_type'] = 'nfs'
                node_info['exports'] = get_nfs_exports(self.context.sysadmin_client, node_info['ipAddress'], vapp, vm_name) # noqa: E501
        if node_info is None:
            raise e.NodeNotFoundError(f"Node '{node_name}' not found in "
                                      f"cluster '{cluster_name}'")
        return node_info

    def create_nodes(self, cluster_id: str,
                     cluster_spec: def_models.ClusterEntity):
        """Start the create nodes operation.

        :param str cluster_id: Defined entity Id of the cluster
        :param DefEntity cluster_spec: Input cluster spec
        :return: DefEntity of the cluster with the updated operation status
        and task_href.

        :rtype: DefEntity
        """
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
            cluster_id)  # noqa: E501
        cluster_name = cluster_spec.metadata.cluster_name
        num_workers_to_add = cluster_spec.spec.workers.count - curr_entity.entity.spec.workers.count  # noqa: E501
        worker_count = cluster_spec.spec.workers.count

        # Resize using the template with which cluster was originally created.
        template_name = curr_entity.entity.spec.k8_distribution.template_name
        template_revision = curr_entity.entity.spec.k8_distribution.template_revision  # noqa: E501

        # check that requested/default template is valid
        get_template(name=template_name, revision=template_revision)

        if worker_count < 1:
            raise e.CseServerError(f"Worker count must be > 0 "
                                   f"(received {worker_count}).")

        # TODO(DEF) Handle Telemetry for defined entities

        msg = f"Creating {num_workers_to_add} node(s) from template " \
              f"'{template_name}' (revision {template_revision}) and " \
              f"adding to cluster '{cluster_name}' ({cluster_id})"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
        curr_entity.entity.status.task_href = self.task_resource.get('href')
        curr_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.UPDATE,
                           DefEntityOperationStatus.IN_PROGRESS))
        curr_entity = self.entity_svc.update_entity(cluster_id, curr_entity)

        self.context.is_async = True
        self._create_nodes_async(cluster_id=cluster_id, cluster_spec=cluster_spec)  # noqa: E501
        return curr_entity

    def delete_nodes(self, cluster_id: str, nodes_to_del=[]):
        """Start the delete nodes operation."""
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
            cluster_id)

        if len(nodes_to_del) == 0:
            LOGGER.debug("No nodes specified to delete")
            return curr_entity

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None

        msg = f"Deleting {', '.join(nodes_to_del)} node(s) from cluster " \
              f"'{curr_entity.entity.metadata.cluster_name}' ({cluster_id})"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

        # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
        #  based clusters

        curr_entity.entity.status.task_href = self.task_resource.get('href')
        curr_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.UPDATE,
                           DefEntityOperationStatus.IN_PROGRESS))
        curr_entity = self.entity_svc.update_entity(cluster_id, curr_entity)

        self.context.is_async = True
        self._monitor_delete_nodes(cluster_id=cluster_id,
                                   nodes_to_del=nodes_to_del)
        return curr_entity

    @utils.run_async
    def _monitor_delete_nodes(self, cluster_id, nodes_to_del):
        """Triggers and monitors delete thread.

        This method (or) thread waits for the thread(s) to join before
        - updating the defined entity
        - updating the task status to SUCCESS
        - ending the client context
        """
        try:
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
                cluster_id)
            cluster_name: str = curr_entity.name
            self._delete_nodes_async(cluster_id=cluster_id,
                                     nodes_to_del=nodes_to_del)

            # wait for the children threads of the current thread to join
            curr_thread_id = str(threading.current_thread().ident)
            for t in threading.enumerate():
                if t.getName().endswith(curr_thread_id):
                    t.join()

            # update the defined entity and task status.
            curr_task_status = self.task_resource.get('status')
            if curr_task_status == vcd_client.TaskStatus.ERROR.value:
                curr_entity.entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.FAILED))
            else:
                msg = f"Deleted the {nodes_to_del} nodes  from cluster " \
                      f"'{cluster_name}' ({cluster_id}) "
                self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
                curr_entity.entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.SUCCEEDED))
            self._sync_def_entity(cluster_id, curr_entity)
        except Exception as err:
            self._fail_operation_and_resolve_entity(cluster_id,
                                                    DefEntityOperation.UPDATE)
            LOGGER.error(f"Unexpected error while deleting nodes for "
                         f"{cluster_name} ({cluster_id}): {err}",
                         exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              error_message=str(err))
        finally:
            self.context.end()

    @utils.run_async
    def _create_nodes_async(self, cluster_id: str,
                            cluster_spec: def_models.ClusterEntity):
        """Create worker and/or nfs nodes in vCD.

        This method is executed by a thread in an asynchronous manner.
        Do's:
        - Update the defined entity in except blocks.
        - Can set the self.task status either to Running or Error
        Dont's:
        - Do not set the self.task status to SUCCESS. This will prevent other
        parallel threads if any to update the status. vCD interprets SUCCESS
        as a terminal state.
        - Do not end the context.client.

        Let the caller monitor thread or method to set SUCCESS task status,
         end the client context
        """
        try:
            # get the current state of the defined entity
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
            vapp_href = curr_entity.externalId
            cluster_name = curr_entity.entity.metadata.cluster_name
            org_name = curr_entity.entity.metadata.org_name
            ovdc_name = curr_entity.entity.metadata.ovdc_name
            curr_worker_count: int = curr_entity.entity.spec.workers.count
            curr_nfs_count: int = curr_entity.entity.spec.nfs.count

            # use the same settings with which cluster was originally created
            # viz., template, storage_profile, and network among others.
            worker_storage_profile = curr_entity.entity.spec.workers.storage_profile  # noqa: E501
            worker_sizing_class = curr_entity.entity.spec.workers.sizing_class
            nfs_storage_profile = curr_entity.entity.spec.nfs.storage_profile
            nfs_sizing_class = curr_entity.entity.spec.nfs.sizing_class
            network_name = curr_entity.entity.spec.settings.network
            ssh_key = curr_entity.entity.spec.settings.ssh_key
            rollback = cluster_spec.spec.settings.rollback_on_failure
            template_name = curr_entity.entity.spec.k8_distribution.template_name  # noqa: E501
            template_revision = curr_entity.entity.spec.k8_distribution.template_revision  # noqa: E501
            template = get_template(template_name, template_revision)

            # compute the values of workers and nfs to be added or removed
            desired_worker_count: int = cluster_spec.spec.workers.count
            num_workers_to_add = desired_worker_count - curr_worker_count
            desired_nfs_count = cluster_spec.spec.nfs.count
            num_nfs_to_add = desired_nfs_count - curr_nfs_count

            server_config = utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            org = vcd_utils.get_org(self.context.client, org_name=org_name)
            ovdc = vcd_utils.get_vdc(self.context.client, vdc_name=ovdc_name, org=org)  # noqa: E501
            vapp = vcd_vapp.VApp(self.context.client, href=vapp_href)

            if num_workers_to_add > 0:
                msg = f"Creating {num_workers_to_add} workers from template" \
                      f"' {template_name}' (revision {template_revision}); " \
                      f"adding to cluster '{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                worker_nodes = add_nodes(self.context.sysadmin_client,
                                         num_nodes=num_workers_to_add,
                                         node_type=NodeType.WORKER,
                                         org=org,
                                         vdc=ovdc,
                                         vapp=vapp,
                                         catalog_name=catalog_name,
                                         template=template,
                                         network_name=network_name,
                                         storage_profile=worker_storage_profile,  # noqa: E501
                                         ssh_key=ssh_key,
                                         sizing_class_name=worker_sizing_class)
                msg = f"Adding {num_workers_to_add} node(s) to cluster " \
                      f"{cluster_name}({cluster_id})"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                target_nodes = []
                for spec in worker_nodes['specs']:
                    target_nodes.append(spec['target_vm_name'])
                vapp.reload()
                join_cluster(self.context.sysadmin_client,
                             vapp,
                             template[LocalTemplateKey.NAME],
                             template[LocalTemplateKey.REVISION], target_nodes)
                msg = f"Added {num_workers_to_add} node(s) to cluster " \
                      f"{cluster_name}({cluster_id})"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            if num_nfs_to_add > 0:
                msg = f"Creating {num_nfs_to_add} nfs node(s) from template " \
                      f"'{template_name}' (revision {template_revision}) " \
                      f"for cluster '{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                add_nodes(self.context.sysadmin_client,
                          num_nodes=num_nfs_to_add,
                          node_type=NodeType.NFS,
                          org=org,
                          vdc=ovdc,
                          vapp=vapp,
                          catalog_name=catalog_name,
                          template=template,
                          network_name=network_name,
                          storage_profile=nfs_storage_profile,
                          ssh_key=ssh_key,
                          sizing_class_name=nfs_sizing_class)
                msg = f"Created {num_nfs_to_add} nfs_node(s) for cluster " \
                      f"'{cluster_name}' ({cluster_id})"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            msg = f"Created {num_workers_to_add} workers & {num_nfs_to_add}" \
                  f" nfs nodes for '{cluster_name}' ({cluster_id}) "
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        except (e.NodeCreationError, e.ClusterJoiningError) as err:
            LOGGER.error(f"Error adding nodes to cluster '{cluster_name}'",
                         exc_info=True)
            LOGGER.error(str(err), exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              error_message=str(err))
            if rollback:
                msg = f"Error adding nodes to cluster '{cluster_name}' " \
                      f"({cluster_id}). Deleting nodes: {err.node_names} " \
                      f"(rollback=True)"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    _delete_nodes(self.context.sysadmin_client,
                                  vapp_href,
                                  err.node_names,
                                  cluster_name=cluster_name)
                except Exception:
                    LOGGER.error(f"Failed to delete nodes {err.node_names} "
                                 f"from cluster '{cluster_name}'",
                                 exc_info=True)
            self._fail_operation_and_resolve_entity(cluster_id,
                                                    DefEntityOperation.UPDATE,
                                                    vapp)
        except Exception as err:
            self._fail_operation_and_resolve_entity(cluster_id,
                                                    DefEntityOperation.UPDATE,
                                                    vapp)
            LOGGER.error(str(err), exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              error_message=str(err))

    @utils.run_async
    def _delete_nodes_async(self, cluster_id: str,
                            cluster_spec: def_models.ClusterEntity = None,
                            nodes_to_del=[]):
        """Delete worker and/or nfs nodes in vCD.

        This method is executed by a thread in an asynchronous manner.
        Do's:
        - Update the defined entity in except blocks.
        - Set the self.task status either to Running or Error
        Dont's:
        - Do not set the self.task status to SUCCESS. This will prevent other
        parallel threads if any to update the status. vCD interprets SUCCESS
        as a terminal state.
        - Do not end the context.client.

        Let the caller monitor thread or method to set SUCCESS task status,
          end the client context
        """
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
        vapp_href = curr_entity.externalId
        cluster_name = curr_entity.entity.metadata.cluster_name

        if not nodes_to_del:
            if not cluster_spec:
                raise e.CseServerError(f"No nodes specified to delete for "
                                       f"cluster {cluster_name}({cluster_id})")
            desired_worker_count = cluster_spec.spec.workers.count
            nodes_to_del = [node.name for node in
                            curr_entity.entity.status.nodes.workers[desired_worker_count:]]  # noqa: E501

        vapp = vcd_vapp.VApp(self.context.client, href=vapp_href)
        try:
            msg = f"Draining {len(nodes_to_del)} node(s) " \
                  f"from cluster '{cluster_name}': {nodes_to_del}"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

            # if nodes fail to drain, continue with node deletion anyways
            try:
                _drain_nodes(self.context.sysadmin_client,
                             vapp_href,
                             nodes_to_del,
                             cluster_name=cluster_name)
            except (e.NodeOperationError, e.ScriptExecutionError) as err:
                LOGGER.warning(f"Failed to drain nodes: {nodes_to_del}"
                               f" in cluster '{cluster_name}'."
                               f" Continuing node delete...\nError: {err}")

            msg = f"Deleting {len(nodes_to_del)} node(s) from " \
                  f"cluster '{cluster_name}': {nodes_to_del}"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

            _delete_nodes(self.context.sysadmin_client,
                          vapp_href,
                          nodes_to_del,
                          cluster_name=cluster_name)

            msg = f"Deleted {len(nodes_to_del)} node(s)" \
                  f" to cluster '{cluster_name}'"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

        except Exception as err:
            self._fail_operation_and_resolve_entity(cluster_id,
                                                    DefEntityOperation.UPDATE,
                                                    vapp)
            LOGGER.error(f"Unexpected error while deleting nodes "
                         f"{nodes_to_del}: {err}",
                         exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              error_message=str(err))

    @utils.run_async
    def _delete_cluster_async(self, cluster_name, org_name, ovdc_name,
                              def_entity: def_models.DefEntity = None):
        """Delete the cluster asynchronously.

        :param cluster_name: Name of the cluster to be deleted.
        :param org_name: Name of the org where the cluster resides.
        :param ovdc_name: Name of the ovdc where the cluster resides.
        :param def_entity: Previously deleted defined entity object, which
        needs to be recreated in the failure case of cluster vapp deletion.
        """
        try:
            cluster_vdc_href = self._get_vdc_href(org_name, ovdc_name)
            msg = f"Deleting cluster '{cluster_name}'"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            _delete_vapp(self.context.client, cluster_vdc_href, cluster_name)
            msg = f"Deleted cluster '{cluster_name}'"
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
        except Exception as err:
            LOGGER.error(f"Unexpected error while deleting cluster: {err}",
                         exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              error_message=str(err))
        finally:
            self.context.end()

    @utils.run_async
    def _upgrade_cluster_async(self, *args,
                               cluster_id: str,
                               template):
        try:
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id) # noqa: E501
            cluster_name = curr_entity.entity.metadata.cluster_name
            vapp_href = curr_entity.externalId

            # TODO use cluster status field to get the master and worker nodes
            vapp = vcd_vapp.VApp(self.context.client, href=vapp_href)
            all_node_names = [vm.get('name') for vm in vapp.get_all_vms()]
            master_node_names = [curr_entity.entity.status.nodes.master.name]
            worker_node_names = [worker.name for worker in curr_entity.entity.status.nodes.workers]  # noqa: E501

            template_name = template[LocalTemplateKey.NAME]
            template_revision = template[LocalTemplateKey.REVISION]

            # semantic version doesn't allow leading zeros
            # docker's version format YY.MM.patch allows us to directly use
            # lexicographical string comparison
            c_docker = curr_entity.entity.status.docker_version
            t_docker = template[LocalTemplateKey.DOCKER_VERSION]
            k8s_details = curr_entity.entity.status.kubernetes.split(' ')
            c_k8s = semver.Version(k8s_details[1])
            t_k8s = semver.Version(template[LocalTemplateKey.KUBERNETES_VERSION]) # noqa: E501
            cni_details = curr_entity.entity.status.cni.split(' ')
            c_cni = semver.Version(cni_details[1])
            t_cni = semver.Version(template[LocalTemplateKey.CNI_VERSION])

            upgrade_docker = t_docker > c_docker
            upgrade_k8s = t_k8s >= c_k8s
            upgrade_cni = t_cni > c_cni or t_k8s.major > c_k8s.major or t_k8s.minor > c_k8s.minor # noqa: E501

            if upgrade_k8s:
                msg = f"Draining master node {master_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _drain_nodes(self.context.sysadmin_client, vapp_href,
                             master_node_names, cluster_name=cluster_name)

                msg = f"Upgrading Kubernetes ({c_k8s} -> {t_k8s}) " \
                      f"in master node {master_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.MASTER_K8S_UPGRADE) # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                run_script_in_nodes(self.context.sysadmin_client, vapp_href,
                                    master_node_names, script)

                msg = f"Uncordoning master node {master_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _uncordon_nodes(self.context.sysadmin_client,
                                vapp_href,
                                master_node_names,
                                cluster_name=cluster_name)

                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.WORKER_K8S_UPGRADE) # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                for node in worker_node_names:
                    msg = f"Draining node {node}"
                    self._update_task(vcd_client.TaskStatus.RUNNING,
                                      message=msg)
                    _drain_nodes(self.context.sysadmin_client,
                                 vapp_href,
                                 [node],
                                 cluster_name=cluster_name)

                    msg = f"Upgrading Kubernetes ({c_k8s} " \
                          f"-> {t_k8s}) in node {node}"
                    self._update_task(vcd_client.TaskStatus.RUNNING,
                                      message=msg)
                    run_script_in_nodes(self.context.sysadmin_client,
                                        vapp_href, [node], script)

                    msg = f"Uncordoning node {node}"
                    self._update_task(vcd_client.TaskStatus.RUNNING,
                                      message=msg)
                    _uncordon_nodes(self.context.sysadmin_client,
                                    vapp_href, [node],
                                    cluster_name=cluster_name)

            if upgrade_docker or upgrade_cni:
                msg = f"Draining all nodes {all_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _drain_nodes(self.context.sysadmin_client,
                             vapp_href, all_node_names,
                             cluster_name=cluster_name)

            if upgrade_docker:
                msg = f"Upgrading Docker-CE ({c_docker} -> {t_docker}) " \
                      f"in nodes {all_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.DOCKER_UPGRADE)
                script = utils.read_data_file(filepath, logger=LOGGER)
                run_script_in_nodes(self.context.sysadmin_client, vapp_href,
                                    all_node_names, script)

            if upgrade_cni:
                msg = "Applying CNI " \
                      f"({curr_entity.entity.status.cni} " \
                      f"-> {t_cni}) in master node {master_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.MASTER_CNI_APPLY)
                script = utils.read_data_file(filepath, logger=LOGGER)
                run_script_in_nodes(self.context.sysadmin_client, vapp_href,
                                    master_node_names, script)

            # uncordon all nodes (sometimes redundant)
            msg = f"Uncordoning all nodes {all_node_names}"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            _uncordon_nodes(self.context.sysadmin_client, vapp_href,
                            all_node_names, cluster_name=cluster_name)

            # update cluster metadata
            msg = f"Updating metadata for cluster '{cluster_name}'"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            metadata = {
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME], # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION], # noqa: E501
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION], # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION], # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION] # noqa: E501
            }

            task = vapp.set_multiple_metadata(metadata)
            self.context.client.get_task_monitor().wait_for_status(task)

            # update defined entity of the cluster
            curr_entity.entity.spec.k8_distribution.template_name = \
                template[LocalTemplateKey.NAME]
            curr_entity.entity.spec.k8_distribution.template_revision = \
                int(template[LocalTemplateKey.REVISION])
            curr_entity.entity.status.cni = \
                _create_k8s_software_string(template[LocalTemplateKey.CNI],
                                            template[LocalTemplateKey.CNI_VERSION]) # noqa: E501
            curr_entity.entity.status.kubernetes = \
                _create_k8s_software_string(template[LocalTemplateKey.KUBERNETES], # noqa: E501
                                            template[LocalTemplateKey.KUBERNETES_VERSION]) # noqa: E501
            curr_entity.entity.status.docker_version = template[LocalTemplateKey.DOCKER_VERSION] # noqa: E501
            curr_entity.entity.status.os = template[LocalTemplateKey.OS]
            curr_entity.entity.status.phase = str(
                DefEntityPhase(DefEntityOperation.UPGRADE,
                               DefEntityOperationStatus.SUCCEEDED))
            self.entity_svc.update_entity(curr_entity.id, curr_entity)

            msg = f"Successfully upgraded cluster '{cluster_name}' software " \
                  f"to match template {template_name} (revision " \
                  f"{template_revision}): Kubernetes: {c_k8s} -> {t_k8s}, " \
                  f"Docker-CE: {c_docker} -> {t_docker}, " \
                  f"CNI: {c_cni} -> {t_cni}"
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
            LOGGER.info(f"{msg} ({vapp_href})")
        except Exception as err:
            self._fail_operation_and_resolve_entity(cluster_id,
                                                    DefEntityOperation.UPGRADE,
                                                    vapp)
            msg = f"Unexpected error while upgrading cluster " \
                  f"'{cluster_name}': {err}"
            LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR, error_message=msg)

        finally:
            self.context.end()

    def _update_task(self, status, message='', error_message=None,
                     stack_trace=''):
        """Update task or create it if it does not exist.

        This function should only be used in the x_async functions, or in the
        6 common broker functions to create the required task.
        When this function is used, it logs in the sys admin client if it is
        not already logged in, but it does not log out. This is because many
        _update_task() calls are used in sequence until the task succeeds or
        fails. Once the task is updated to a success or failure state, then
        the sys admin client should be logged out.

        Another reason for decoupling sys admin logout and this function is
        because if any unknown errors occur during an operation, there should
        be a finally clause that takes care of logging out.
        """
        if not self.context.client.is_sysadmin():
            stack_trace = ''

        if self.task is None:
            self.task = vcd_task.Task(self.context.sysadmin_client)

        org = vcd_utils.get_org(self.context.client)
        user_href = org.get_user(self.context.user.name).get('href')

        # Wait for the thread-1 to finish updating the task, before thread-2 in
        # the line can read the current status of the task.
        # It is safe for thread-2 to check the current task status before
        # updating it. A task with a terminal state of SUCCESS or ERROR cannot
        # be further updated; vCD will throw an error.
        with self.task_update_lock:
            task_href = None
            if self.task_resource is not None:
                task_href = self.task_resource.get('href')
                curr_task_status = self.task_resource.get('status')
                if curr_task_status == vcd_client.TaskStatus.SUCCESS.value or \
                        curr_task_status == vcd_client.TaskStatus.ERROR.value:
                    # TODO Log the message here.
                    return
            self.task_resource = self.task.update(
                status=status.value,
                namespace='vcloud.cse',
                operation=message,
                operation_name='cluster operation',
                details='',
                progress=None,
                owner_href=self.context.user.org_href,
                owner_name=self.context.user.org_name,
                owner_type='application/vnd.vmware.vcloud.org+xml',
                user_href=user_href,
                user_name=self.context.user.name,
                org_href=self.context.user.org_href,
                task_href=task_href,
                error_message=error_message,
                stack_trace=stack_trace
            )


def _drain_nodes(sysadmin_client: vcd_client.Client, vapp_href, node_names,
                 cluster_name=''):
    LOGGER.debug(f"Draining nodes {node_names} in cluster '{cluster_name}' "
                 f"(vapp: {vapp_href})")
    script = "#!/usr/bin/env bash\n"
    for node_name in node_names:
        script += f"kubectl drain {node_name} " \
                  f"--ignore-daemonsets --timeout=60s --delete-local-data\n"

    try:
        vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
        master_node_names = get_node_names(vapp, NodeType.MASTER)
        run_script_in_nodes(sysadmin_client, vapp_href, [master_node_names[0]],
                            script)
    except Exception as err:
        LOGGER.warning(f"Failed to drain nodes {node_names} in cluster "
                       f"'{cluster_name}' (vapp: {vapp_href}) with "
                       f"error: {err}")
        raise

    LOGGER.debug(f"Successfully drained nodes {node_names} in cluster "
                 f"'{cluster_name}' (vapp: {vapp_href})")


def _uncordon_nodes(sysadmin_client: vcd_client.Client, vapp_href, node_names,
                    cluster_name=''):
    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)

    LOGGER.debug(f"Uncordoning nodes {node_names} in cluster '{cluster_name}' "
                 f"(vapp: {vapp_href})")
    script = "#!/usr/bin/env bash\n"
    for node_name in node_names:
        script += f"kubectl uncordon {node_name}\n"

    try:
        vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
        master_node_names = get_node_names(vapp, NodeType.MASTER)
        run_script_in_nodes(sysadmin_client, vapp_href, [master_node_names[0]],
                            script)
    except Exception as err:
        LOGGER.warning(f"Failed to uncordon nodes {node_names} in cluster "
                       f"'{cluster_name}' (vapp: {vapp_href}) "
                       f"with error: {err}")
        raise

    LOGGER.debug(f"Successfully uncordoned nodes {node_names} in cluster "
                 f"'{cluster_name}' (vapp: {vapp_href})")


def _delete_vapp(client, vdc_href, vapp_name):
    LOGGER.debug(f"Deleting vapp {vapp_name} (vdc: {vdc_href})")

    try:
        vdc = VDC(client, href=vdc_href)
        task = vdc.delete_vapp(vapp_name, force=True)
        client.get_task_monitor().wait_for_status(task)
    except Exception as err:
        LOGGER.warning(f"Failed to delete vapp {vapp_name} "
                       f"(vdc: {vdc_href}) with error: {err}")
        raise

    LOGGER.debug(f"Deleted vapp {vapp_name} (vdc: {vdc_href})")


def _delete_nodes(sysadmin_client: vcd_client.Client, vapp_href, node_names,
                  cluster_name=''):
    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)

    LOGGER.debug(f"Deleting node(s) {node_names} from cluster '{cluster_name}'"
                 f" (vapp: {vapp_href})")
    script = "#!/usr/bin/env bash\nkubectl delete node "
    are_there_workers_to_del = False
    for node_name in node_names:
        if node_name.startswith(NodeType.WORKER):
            script += f' {node_name}'
            are_there_workers_to_del = True
    script += '\n'

    vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)

    try:
        if are_there_workers_to_del:
            master_node_names = get_node_names(vapp, NodeType.MASTER)
            run_script_in_nodes(sysadmin_client, vapp_href,
                                [master_node_names[0]], script)
    except Exception as err:
        LOGGER.warning(f"Failed to delete node(s) {node_names} from cluster "
                       f"'{cluster_name}' using kubectl (vapp: {vapp_href}): {err}")  # noqa: E501

    vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
    vapp.reload()
    for vm_name in node_names:
        vm = vcd_vm.VM(sysadmin_client, resource=vapp.get_vm(vm_name))
        try:
            task = vm.undeploy()
            sysadmin_client.get_task_monitor().wait_for_status(task)
        except Exception:
            LOGGER.warning(f"Failed to undeploy VM {vm_name} "
                           f"(vapp: {vapp_href})")

    task = vapp.delete_vms(node_names)
    sysadmin_client.get_task_monitor().wait_for_status(task)
    LOGGER.debug(f"Successfully deleted node(s) {node_names} from "
                 f"cluster '{cluster_name}' (vapp: {vapp_href})")


def get_nfs_exports(sysadmin_client: vcd_client.Client, ip, vapp, vm_name):
    """Get the exports from remote NFS server.

    :param pyvcloud.vcd.client.Client sysadmin_client:
    :param str ip: IP address of the NFS server
    :param pyvcloud.vcd.vapp.vcd_vapp.VApp vapp:
    :param str vm_name:

    :return: (List): List of exports
    """
    script = f"#!/usr/bin/env bash\nshowmount -e {ip}"
    result = execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                     node_names=[vm_name], script=script,
                                     check_tools=False)
    lines = result[0][1].content.decode().split('\n')
    exports = []
    for index in range(1, len(lines) - 1):
        export = lines[index].strip().split()[0]
        exports.append(export)
    return exports


def is_valid_cluster_name(name):
    """Validate that the cluster name against the pattern."""
    if len(name) > 25:
        return False
    if name[-1] == '.':
        name = name[:-1]
    allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in name.split("."))


def get_all_clusters(client, cluster_name=None, cluster_id=None,
                     org_name=None, ovdc_name=None):
    """Get list of dictionaries containing data for each visible cluster.

    TODO define these cluster data dictionary keys better:
        'name', 'vapp_id', 'vapp_href', 'vdc_name', 'vdc_href', 'vdc_id',
        'leader_endpoint', 'master_nodes', 'nodes', 'nfs_nodes',
        'number_of_vms', 'template_name', 'template_revision',
        'cse_version', 'cluster_id', 'status', 'os', 'docker_version',
        'kubernetes', 'kubernetes_version', 'cni', 'cni_version'
    """
    query_filter = f'metadata:{ClusterMetadataKey.CLUSTER_ID}==STRING:*'
    if cluster_id is not None:
        query_filter = f'metadata:{ClusterMetadataKey.CLUSTER_ID}==STRING:{cluster_id}' # noqa: E501
    if cluster_name is not None:
        query_filter += f';name=={cluster_name}'
    if ovdc_name is not None:
        query_filter += f";vdcName=={ovdc_name}"
    resource_type = 'vApp'
    if client.is_sysadmin():
        resource_type = 'adminVApp'
        if org_name is not None and org_name.lower() != SYSTEM_ORG_NAME.lower(): # noqa: E501
            org_resource = client.get_org_by_name(org_name)
            org = vcd_org.Org(client, resource=org_resource)
            query_filter += f";org=={org.resource.get('id')}"

    # 2 queries are required because each query can only return 8 metadata
    q = client.get_typed_query(
        resource_type,
        query_result_format=vcd_client.QueryResultFormat.ID_RECORDS,
        qfilter=query_filter,
        fields=f'metadata:{ClusterMetadataKey.CLUSTER_ID}'
               f',metadata:{ClusterMetadataKey.MASTER_IP}'
               f',metadata:{ClusterMetadataKey.CSE_VERSION}'
               f',metadata:{ClusterMetadataKey.TEMPLATE_NAME}'
               f',metadata:{ClusterMetadataKey.TEMPLATE_REVISION}'
               f',metadata:{ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME}' # noqa: E501
               f',metadata:{ClusterMetadataKey.OS}')
    q2 = client.get_typed_query(
        resource_type,
        query_result_format=vcd_client.QueryResultFormat.ID_RECORDS,
        qfilter=query_filter,
        fields=f'metadata:{ClusterMetadataKey.DOCKER_VERSION}'
               f',metadata:{ClusterMetadataKey.KUBERNETES}'
               f',metadata:{ClusterMetadataKey.KUBERNETES_VERSION}'
               f',metadata:{ClusterMetadataKey.CNI}'
               f',metadata:{ClusterMetadataKey.CNI_VERSION}')

    metadata_key_to_cluster_key = {
        ClusterMetadataKey.CLUSTER_ID: 'cluster_id',
        ClusterMetadataKey.CSE_VERSION: 'cse_version',
        ClusterMetadataKey.MASTER_IP: 'leader_endpoint',
        ClusterMetadataKey.TEMPLATE_NAME: 'template_name',
        ClusterMetadataKey.TEMPLATE_REVISION: 'template_revision',
        ClusterMetadataKey.OS: 'os',
        ClusterMetadataKey.DOCKER_VERSION: 'docker_version',
        ClusterMetadataKey.KUBERNETES: 'kubernetes',
        ClusterMetadataKey.KUBERNETES_VERSION: 'kubernetes_version',
        ClusterMetadataKey.CNI: 'cni',
        ClusterMetadataKey.CNI_VERSION: 'cni_version'
    }

    clusters = {}
    for record in q.execute():
        vapp_id = record.get('id').split(':')[-1]
        vdc_id = record.get('vdc').split(':')[-1]
        vapp_href = f'{client.get_api_uri()}/vApp/vapp-{vapp_id}'

        clusters[vapp_id] = {
            'name': record.get('name'),
            'vapp_id': vapp_id,
            'vapp_href': vapp_href,
            'vdc_name': record.get('vdcName'),
            'vdc_href': f'{client.get_api_uri()}/vdc/{vdc_id}',
            'vdc_id': vdc_id,
            'leader_endpoint': '',
            'master_nodes': [],
            'nodes': [],
            'nfs_nodes': [],
            'number_of_vms': record.get('numberOfVMs'),
            'template_name': '',
            'template_revision': '',
            'cse_version': '',
            'cluster_id': '',
            'status': record.get('status'),
            'os': '',
            'docker_version': '',
            'kubernetes': '',
            'kubernetes_version': '',
            'cni': '',
            'cni_version': ''
        }

        if hasattr(record, 'Metadata'):
            for element in record.Metadata.MetadataEntry:
                if element.Key in metadata_key_to_cluster_key:
                    clusters[vapp_id][metadata_key_to_cluster_key[element.Key]] = str(element.TypedValue.Value) # noqa: E501
                # for pre-2.5.0 cluster backwards compatibility
                elif element.Key == ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME and clusters[vapp_id]['template_name'] == '': # noqa: E501
                    clusters[vapp_id]['template_name'] = str(element.TypedValue.Value) # noqa: E501

        # pre-2.6 clusters may not have kubernetes version metadata
        if clusters[vapp_id]['kubernetes_version'] == '':
            clusters[vapp_id]['kubernetes_version'] = ltm.get_k8s_version_from_template_name(clusters[vapp_id]['template_name']) # noqa: E501

    # api query can fetch only 8 metadata at a time
    # since we have more than 8 metadata, we need to use 2 queries
    for record in q2.execute():
        vapp_id = record.get('id').split(':')[-1]
        if hasattr(record, 'Metadata'):
            for element in record.Metadata.MetadataEntry:
                if element.Key in metadata_key_to_cluster_key:
                    clusters[vapp_id][metadata_key_to_cluster_key[element.Key]] = str(element.TypedValue.Value) # noqa: E501
                # for pre-2.5.0 cluster backwards compatibility
                elif element.Key == ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME and clusters[vapp_id]['template_name'] == '': # noqa: E501
                    clusters[vapp_id]['template_name'] = str(element.TypedValue.Value) # noqa: E501

    return list(clusters.values())


def get_cluster(client, cluster_name, cluster_id=None, org_name=None,
                ovdc_name=None):
    clusters = get_all_clusters(client, cluster_name=cluster_name,
                                cluster_id=cluster_id, org_name=org_name,
                                ovdc_name=ovdc_name)
    if len(clusters) > 1:
        raise e.CseDuplicateClusterError(f"Found multiple clusters named"
                                         f" '{cluster_name}'.")
    if len(clusters) == 0:
        raise e.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")

    return clusters[0]


def get_template(name=None, revision=None):
    if (name is None and revision is not None) or (name is not None and revision is None): # noqa: E501
        raise ValueError("If template revision is specified, then template "
                         "name must also be specified (and vice versa).")
    server_config = utils.get_server_runtime_config()
    name = name or server_config['broker']['default_template_name']
    revision = revision or server_config['broker']['default_template_revision']
    for template in server_config['broker']['templates']:
        if template[LocalTemplateKey.NAME] == name and str(template[LocalTemplateKey.REVISION]) == str(revision): # noqa: E501
            return template
    raise Exception(f"Template '{name}' at revision {revision} not found.")


def add_nodes(sysadmin_client, num_nodes, node_type, org, vdc, vapp,
              catalog_name, template, network_name, storage_profile=None,
              ssh_key=None, sizing_class_name=None):
    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)

    if num_nodes > 0:
        specs = []
        try:
            # DEV NOTE: With api v33.0 and onwards, get_catalog operation will fail  # noqa: E501
            # for non admin users of an an org which is not hosting the catalog,  # noqa: E501
            # even if the catalog is explicitly shared with the org in question.  # noqa: E501
            # This happens because for api v 33.0 and onwards, the Org XML no
            # longer returns the href to catalogs accessible to the org, and typed  # noqa: E501
            # queries hide the catalog link from non admin users.
            # As a workaround, we will use a sys admin client to get the href and  # noqa: E501
            # pass it forward. Do note that the catalog itself can still be
            # accessed by these non admin users, just that they can't find by the  # noqa: E501
            # href on their own.

            org_name = org.get_name()
            org_resource = sysadmin_client.get_org_by_name(org_name)
            org_sa = vcd_org.Org(sysadmin_client, resource=org_resource)
            catalog_item = org_sa.get_catalog_item(
                catalog_name, template[LocalTemplateKey.CATALOG_ITEM_NAME])
            catalog_item_href = catalog_item.Entity.get('href')

            source_vapp = vcd_vapp.VApp(sysadmin_client, href=catalog_item_href)  # noqa: E501
            source_vm = source_vapp.get_all_vms()[0].get('name')
            if storage_profile is not None:
                storage_profile = vdc.get_storage_profile(storage_profile)

            config = utils.get_server_runtime_config()
            cpm = compute_policy_manager.ComputePolicyManager(sysadmin_client,
                                                              log_wire=utils.str_to_bool(config['service']['log_wire']))  # noqa: E501
            sizing_class_href = None
            if sizing_class_name:
                sizing_class_href = cpm.get_vdc_compute_policy(sizing_class_name)['href']  # noqa: E501
            if storage_profile:
                storage_profile = vdc.get_storage_profile(storage_profile)

            cust_script = None
            if ssh_key is not None:
                cust_script = \
                    "#!/usr/bin/env bash\n" \
                    "if [ x$1=x\"postcustomization\" ];\n" \
                    "then\n" \
                    "mkdir -p /root/.ssh\n" \
                    f"echo '{ssh_key}' >> /root/.ssh/authorized_keys\n" \
                    "chmod -R go-rwx /root/.ssh\n" \
                    "fi"

            vapp.reload()
            for n in range(num_nodes):
                name = None
                while True:
                    name = f"{node_type}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}" # noqa: E501
                    try:
                        vapp.get_vm(name)
                    except Exception:
                        break
                spec = {
                    'source_vm_name': source_vm,
                    'vapp': source_vapp.resource,
                    'target_vm_name': name,
                    'hostname': name,
                    'password_auto': True,
                    'network': network_name,
                    'ip_allocation_mode': 'pool'
                }
                if sizing_class_href:
                    spec['sizing_policy_href'] = sizing_class_href
                if cust_script is not None:
                    spec['cust_script'] = cust_script
                if storage_profile:
                    spec['storage_profile'] = storage_profile
                specs.append(spec)

            task = vapp.add_vms(specs, power_on=False)
            sysadmin_client.get_task_monitor().wait_for_status(task)
            vapp.reload()

            for spec in specs:
                vm_name = spec['target_vm_name']
                vm_resource = vapp.get_vm(vm_name)
                vm = vcd_vm.VM(sysadmin_client, resource=vm_resource)

                task = vm.power_on()
                sysadmin_client.get_task_monitor().wait_for_status(task)
                vapp.reload()

                if node_type == NodeType.NFS:
                    LOGGER.debug(f"Enabling NFS server on {vm_name}")
                    script_filepath = ltm.get_script_filepath(
                        template[LocalTemplateKey.NAME],
                        template[LocalTemplateKey.REVISION],
                        ScriptFile.NFSD)
                    script = utils.read_data_file(script_filepath, logger=LOGGER)  # noqa: E501
                    exec_results = execute_script_in_nodes(
                        sysadmin_client, vapp=vapp, node_names=[vm_name],
                        script=script)
                    errors = get_script_execution_errors(exec_results)
                    if errors:
                        raise e.ScriptExecutionError(
                            f"VM customization script execution failed "
                            f"on node {vm_name}:{errors}")
        except Exception as err:
            # TODO: get details of the exception to determine cause of failure,
            # e.g. not enough resources available.
            node_list = [entry.get('target_vm_name') for entry in specs]
            raise e.NodeCreationError(node_list, str(err))

        vapp.reload()
        return {'task': task, 'specs': specs}


def get_node_names(vapp, node_type):
    return [vm.get('name') for vm in vapp.get_all_vms() if vm.get('name').startswith(node_type)] # noqa: E501


def _wait_for_tools_ready_callback(message, exception=None):
    LOGGER.debug(f"waiting for guest tools, status: {message}")
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def _wait_for_guest_execution_callback(message, exception=None):
    LOGGER.debug(message)
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def get_master_ip(sysadmin_client: vcd_client.Client, vapp):
    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)

    LOGGER.debug(f"Getting master IP for vapp: "
                 f"{vapp.get_resource().get('name')}")
    script = "#!/usr/bin/env bash\n" \
             "ip route get 1 | awk '{print $NF;exit}'\n" \

    node_names = get_node_names(vapp, NodeType.MASTER)
    result = execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                     node_names=node_names, script=script,
                                     check_tools=False)
    errors = get_script_execution_errors(result)
    if errors:
        raise e.ScriptExecutionError(f"Get master IP script execution failed "
                                     f"on master node {node_names}:{errors}")
    master_ip = result[0][1].content.decode().split()[0]
    LOGGER.debug(f"Retrieved master IP for vapp: "
                 f"{vapp.get_resource().get('name')}, ip: {master_ip}")
    return master_ip


def init_cluster(sysadmin_client: vcd_client.Client, vapp, template_name,
                 template_revision):
    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)

    try:
        script_filepath = ltm.get_script_filepath(template_name,
                                                  template_revision,
                                                  ScriptFile.MASTER)
        script = utils.read_data_file(script_filepath, logger=LOGGER)
        node_names = get_node_names(vapp, NodeType.MASTER)
        result = execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                         node_names=node_names, script=script)
        errors = get_script_execution_errors(result)
        if errors:
            raise e.ScriptExecutionError(
                f"Initialize cluster script execution failed on node "
                f"{node_names}:{errors}")
        if result[0][0] != 0:
            raise e.ClusterInitializationError(f"Couldn't initialize cluster:\n{result[0][2].content.decode()}") # noqa: E501
    except Exception as err:
        LOGGER.error(err, exc_info=True)
        raise e.ClusterInitializationError(
            f"Couldn't initialize cluster: {str(err)}")


def join_cluster(sysadmin_client: vcd_client.Client, vapp, template_name,
                 template_revision, target_nodes=None):
    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)
    script = "#!/usr/bin/env bash\n" \
             "kubeadm token create\n" \
             "ip route get 1 | awk '{print $NF;exit}'\n"
    node_names = get_node_names(vapp, NodeType.MASTER)
    master_result = execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                            node_names=node_names,
                                            script=script)
    errors = get_script_execution_errors(master_result)
    if errors:
        raise e.ClusterJoiningError(
            f"Join cluster script execution failed on master node {node_names}:{errors}")  # noqa: E501
    init_info = master_result[0][1].content.decode().split()

    node_names = get_node_names(vapp, NodeType.WORKER)
    if target_nodes is not None:
        node_names = [name for name in node_names if name in target_nodes]
    tmp_script_filepath = ltm.get_script_filepath(template_name,
                                                  template_revision,
                                                  ScriptFile.NODE)
    tmp_script = utils.read_data_file(tmp_script_filepath, logger=LOGGER)
    script = tmp_script.format(token=init_info[0], ip=init_info[1])
    worker_results = execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                             node_names=node_names,
                                             script=script)
    errors = get_script_execution_errors(worker_results)
    if errors:
        raise e.ClusterJoiningError(
            f"Join cluster script execution failed on worker node  {node_names}:{errors}")  # noqa: E501
    for result in worker_results:
        if result[0] != 0:
            raise e.ClusterJoiningError(f"Couldn't join cluster:"
                                        f"\n{result[2].content.decode()}")


def _wait_until_ready_to_exec(vs, vm, password, tries=30):
    ready = False
    script = "#!/usr/bin/env bash\n" \
             "uname -a\n"
    for _ in range(tries):
        result = vs.execute_script_in_guest(
            vm, 'root', password, script,
            target_file=None,
            wait_for_completion=True,
            wait_time=5,
            get_output=True,
            delete_script=True,
            callback=_wait_for_guest_execution_callback)
        if result[0] == 0:
            ready = True
            break
        LOGGER.info(f"Script returned {result[0]}; VM is not "
                    f"ready to execute scripts, yet")
        time.sleep(2)

    if not ready:
        raise e.CseServerError('VM is not ready to execute scripts')


def execute_script_in_nodes(sysadmin_client: vcd_client.Client,
                            vapp, node_names, script,
                            check_tools=True, wait=True):
    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)
    all_results = []
    for node_name in node_names:
        LOGGER.debug(f"will try to execute script on {node_name}:\n"
                     f"{script}")

        vs = vs_utils.get_vsphere(sysadmin_client, vapp, vm_name=node_name,
                                  logger=LOGGER)
        vs.connect()
        moid = vapp.get_vm_moid(node_name)
        vm = vs.get_vm_by_moid(moid)
        password = vapp.get_admin_password(node_name)
        if check_tools:
            LOGGER.debug(f"waiting for tools on {node_name}")
            vs.wait_until_tools_ready(
                vm,
                sleep=5,
                callback=_wait_for_tools_ready_callback)
            _wait_until_ready_to_exec(vs, vm, password)
        LOGGER.debug(f"about to execute script on {node_name} "
                     f"(vm={vm}), wait={wait}")
        if wait:
            result = vs.execute_script_in_guest(
                vm, 'root', password, script,
                target_file=None,
                wait_for_completion=True,
                wait_time=10,
                get_output=True,
                delete_script=True,
                callback=_wait_for_guest_execution_callback)
            result_stdout = result[1].content.decode()
            result_stderr = result[2].content.decode()
        else:
            result = [
                vs.execute_program_in_guest(vm, 'root', password, script,
                                            wait_for_completion=False,
                                            get_output=False)
            ]
            result_stdout = ''
            result_stderr = ''
        LOGGER.debug(result[0])
        LOGGER.debug(result_stderr)
        LOGGER.debug(result_stdout)
        all_results.append(result)

    return all_results


def run_script_in_nodes(sysadmin_client: vcd_client.Client, vapp_href,
                        node_names, script):
    """Run script in all specified nodes.

    Wrapper around `execute_script_in_nodes()`. Use when we don't care about
    preserving script results

    :param pyvcloud.vcd.client.Client sysadmin_client:
    :param str vapp_href:
    :param List[str] node_names:
    :param str script:
    """
    vcd_utils.raise_error_if_not_sysadmin(sysadmin_client)

    # when is tools checking necessary?
    vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
    results = execute_script_in_nodes(sysadmin_client,
                                      vapp=vapp,
                                      node_names=node_names,
                                      script=script,
                                      check_tools=False)
    errors = get_script_execution_errors(results)
    if errors:
        raise e.ScriptExecutionError(f"Script execution failed on node "
                                     f"{node_names}\nErrors: {errors}")
    if results[0][0] != 0:
        raise e.NodeOperationError(f"Error during node operation:\n"
                                   f"{results[0][2].content.decode()}")


def get_script_execution_errors(results):
    return [result[2].content.decode() for result in results if result[0] != 0]


def _create_k8s_software_string(software_name: str, software_version: str) -> str: # noqa: E501
    """Generate string containing the software name and version.

    Example: if software_name is "upstream" and version is "1.17.3",
        "upstream 1.17.3" is returned

    :param str software_name:
    :param str software_version:
    :rtype: str
    """
    return f"{software_name} {software_version}"
