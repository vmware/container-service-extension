# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Utility methods to help interaction with defined entities framework."""
import math
from typing import Union

from container_service_extension.common.constants.server_constants import FlattenedClusterSpecKey  # noqa: E501
from container_service_extension.common.constants.server_constants import VALID_UPDATE_FIELDS  # noqa: E501
import container_service_extension.common.utils.core_utils as core_utils
import container_service_extension.exception.exceptions as excptn
from container_service_extension.exception.exceptions import BadRequestError
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
import container_service_extension.rde.constants as def_constants
import container_service_extension.rde.models.rde_1_0_0 as rde_1_0_0
import container_service_extension.rde.models.rde_2_0_0 as rde_2_0_0


def raise_error_if_def_not_supported(cloudapi_client: CloudApiClient):
    """Raise DefNotSupportedException if defined entities are not supported.

    :param cloudapi_client CloudApiClient
    """
    if float(cloudapi_client.get_api_version()) < \
            def_constants.DEF_API_MIN_VERSION:
        raise excptn.DefNotSupportedException("Defined entity framework is not"
                                              " supported for {cloudapi_client.get_api_version()}")  # noqa: E501


def generate_interface_id(vendor, nss, version):
    """Generate defined entity interface id.

    By no means, id generation in this method, guarantees the actual
    entity type registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{def_constants.DEF_INTERFACE_ID_PREFIX}:{vendor}:{nss}:{version}"


def generate_entity_type_id(vendor, nss, version):
    """Generate defined entity type id.

    By no means, id generation in this method, guarantees the actual
    interface registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{def_constants.DEF_ENTITY_TYPE_ID_PREFIX}:{vendor}:{nss}:{version}"  # noqa: E501


def get_rde_version_by_vcd_api_version(vcd_api_version: float) -> str:
    major_vcd_api_version = math.floor(vcd_api_version)
    return def_constants.MAP_VCD_API_VERSION_TO_RDE_VERSION[major_vcd_api_version]  # noqa: E501


def get_rde_metadata(rde_version: str) -> dict:
    return def_constants.MAP_RDE_VERSION_TO_ITS_METADATA[rde_version]


def construct_cluster_spec_from_entity_status(entity_status: Union[rde_1_0_0.Status, rde_2_0_0.Status], rde_version_in_use: str) -> Union[rde_1_0_0.ClusterSpec, rde_2_0_0.ClusterSpec]:  # noqa: E501
    """Construct cluster specification from entity status of given rde version.

    :param rde_X_X_X Status entity_status: Entity Status of rde of given version  # noqa: E501
    :param str rde_version_in_use: which version of schema
    :return: Cluster Specification of respective rde_version_in_use
    :raises NotImplementedError
    """
    # TODO: Refactor this multiple if to rde_version -> handler pattern
    if rde_version_in_use == '2.0.0':
        return construct_2_x_cluster_spec_from_entity_status(entity_status)
    raise NotImplementedError(f"constructing cluster spec from entity status for {rde_version_in_use} is"  # noqa:
                              f" not implemented ")


def construct_2_x_cluster_spec_from_entity_status(entity_status: rde_2_0_0.Status) -> rde_2_0_0.ClusterSpec:  # noqa:
    """Construct cluster specification from entity status using rde_2_0_0 model.

    :param rde_2_0_0.Status entity_status: Entity Status as defined in rde_2_0_0  # noqa: E501
    :return: Cluster Specification as defined in rde_2_0_0 model
    """
    # Currently only single control-plane is supported.
    control_plane = rde_2_0_0.ControlPlane(
        sizing_class=entity_status.nodes.control_plane.sizing_class,
        storage_profile=entity_status.nodes.control_plane.storage_profile,
        count=1)

    workers_count = len(entity_status.nodes.workers)
    if workers_count == 0:
        workers = rde_2_0_0.Workers(sizing_class=None, storage_profile='*',
                                    count=workers_count)
    else:
        workers = rde_2_0_0.Workers(
            sizing_class=entity_status.nodes.workers[0].sizing_class,
            storage_profile=entity_status.nodes.workers[0].storage_profile,
            count=workers_count)

    nfs_count = len(entity_status.nodes.nfs)
    if nfs_count == 0:
        nfs = rde_2_0_0.Nfs(sizing_class=None, storage_profile='*',
                            count=nfs_count)
    else:
        nfs = rde_2_0_0.Nfs(
            sizing_class=entity_status.nodes.nfs[0].sizing_class,  # noqa: E501
            storage_profile=entity_status.nodes.nfs[
                0].storage_profile)

    k8_distribution = rde_2_0_0.Distribution(
        template_name=entity_status.cloud_properties.k8_distribution.template_name,  # noqa: E501
        template_revision=entity_status.cloud_properties.k8_distribution.template_revision)  # noqa: E501

    settings = rde_2_0_0.Settings(
        network=entity_status.cloud_properties.ovdc_network_name,
        ssh_key=entity_status.cloud_properties.ssh_key,
        rollback_on_failure=entity_status.cloud_properties.rollback_on_failure)  # noqa: E501

    return rde_2_0_0.ClusterSpec(settings=settings,
                                 k8_distribution=k8_distribution,
                                 control_plane=control_plane,
                                 workers=workers,
                                 nfs=nfs)


def validate_cluster_update_request_and_check_cluster_upgrade(input_spec: dict, reference_spec: dict) -> bool:  # noqa: E501
    """Validate the desired spec with curr spec and check if upgrade operation.

    :param dict input_spec: input spec
    :param dict reference_spec: reference spec to validate the desired spec
    :return: true if cluster operation is upgrade and false if operation is
        resize
    :rtype: bool
    :raises: BadRequestError for invalid payload.
    """
    diff_fields = \
        find_diff_fields(input_spec, reference_spec, exclude_fields=[])

    # Raise exception if empty diff
    if not diff_fields:
        raise BadRequestError("No change in cluster specification")  # noqa: E501

    # Raise exception if fields which cannot be changed are updated
    keys_with_invalid_value = [k for k in diff_fields if k not in VALID_UPDATE_FIELDS]  # noqa: E501
    if len(keys_with_invalid_value) > 0:
        err_msg = f"Invalid input values found in {sorted(keys_with_invalid_value)}"  # noqa: E501
        raise BadRequestError(err_msg)

    is_resize_operation = False
    if FlattenedClusterSpecKey.WORKERS_COUNT.value in diff_fields or \
            FlattenedClusterSpecKey.NFS_COUNT.value in diff_fields:
        is_resize_operation = True
    is_upgrade_operation = False
    if FlattenedClusterSpecKey.TEMPLATE_NAME.value in diff_fields or \
            FlattenedClusterSpecKey.TEMPLATE_REVISION.value in diff_fields:
        is_upgrade_operation = True

    # Raise exception if resize and upgrade are performed at the same time
    if is_resize_operation and is_upgrade_operation:
        err_msg = "Cannot resize and upgrade the cluster at the same time"
        raise BadRequestError(err_msg)

    return is_upgrade_operation


def find_diff_fields(input_spec: dict, reference_spec: dict, exclude_fields: list = None) -> list:  # noqa: E501
    if exclude_fields is None:
        exclude_fields = []
    input_dict = core_utils.flatten_dictionary(input_spec)
    reference_dict = core_utils.flatten_dictionary(reference_spec)
    exclude_key_set = set(exclude_fields)
    key_set_for_validation = set(input_dict.keys()) - exclude_key_set
    return [key for key in key_set_for_validation
            if input_dict.get(key) != reference_dict.get(key)]
