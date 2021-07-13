# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Utility methods to help interaction with defined entities framework."""
import importlib
from importlib import resources as pkg_resources
import json
import math
from typing import Type
from typing import Union

import semantic_version

import container_service_extension.common.utils.core_utils as core_utils
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.exception.exceptions as exceptions
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
import container_service_extension.rde.constants as def_constants
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.rde_1_0_0 as rde_1_0_0
import container_service_extension.rde.models.rde_2_0_0 as rde_2_0_0
import container_service_extension.rde.models.rde_factory as rde_factory


def raise_error_if_def_not_supported(cloudapi_client: CloudApiClient):
    """Raise DefNotSupportedException if defined entities are not supported.

    :param cloudapi_client CloudApiClient
    """
    if float(cloudapi_client.get_api_version()) < \
            def_constants.DEF_API_MIN_VERSION:
        raise exceptions.DefNotSupportedException(
            "Defined entity framework is not"
            " supported for {cloudapi_client.get_api_version()}")


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


def get_runtime_rde_version_by_vcd_api_version(vcd_api_version: str) -> str:
    major_vcd_api_version = str(math.floor(float(vcd_api_version)) * 1.0)
    val = def_constants.MAP_VCD_API_VERSION_TO_RUNTIME_RDE_VERSION.get(major_vcd_api_version)  # noqa: E501
    if not val:
        val = '0.0.0'
    return val


def get_rde_version_introduced_at_api_version(vcd_api_version: str) -> str:
    return def_constants.MAP_VCD_API_VERSION_TO_RDE_VERSION[vcd_api_version]


def get_rde_metadata(rde_version: str) -> dict:
    from container_service_extension.rde.models.common_models import MAP_RDE_VERSION_TO_ITS_METADATA  # noqa: E501
    return MAP_RDE_VERSION_TO_ITS_METADATA[rde_version]


def construct_cluster_spec_from_entity_status(entity_status: Union[rde_1_0_0.Status, rde_2_0_0.Status], rde_version: str) -> Union[rde_1_0_0.ClusterSpec, rde_2_0_0.ClusterSpec]:  # noqa: E501
    """Construct cluster spec of the specified rde version from the current status of the cluster.

    :param rde_X_X_X Status entity_status: Entity Status of rde of given version  # noqa: E501
    :param str rde_version: RDE version of the spec to be created from the status # noqa: E501
    :return: Cluster Specification of respective rde_version_in_use
    :raises NotImplementedError
    """
    # TODO: Refactor this multiple if to rde_version -> handler pattern
    if rde_version == def_constants.RDEVersion.RDE_2_0_0.value:
        return construct_2_0_0_cluster_spec_from_entity_status(entity_status)
    # elif rde_version == def_constants.RDEVersion.RDE_2_1_0:
    #    return construct_2_1_0_cluster_spec_from_entity_status(entity_status)
    raise NotImplementedError(f"constructing cluster spec from entity status for {rde_version} is"  # noqa:
                              f" not implemented ")


def construct_2_0_0_cluster_spec_from_entity_status(entity_status: rde_2_0_0.Status) -> rde_2_0_0.ClusterSpec:  # noqa:
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
        workers = rde_2_0_0.Workers(sizing_class=None,
                                    storage_profile=None,
                                    count=0)
    else:
        workers = rde_2_0_0.Workers(
            sizing_class=entity_status.nodes.workers[0].sizing_class,
            storage_profile=entity_status.nodes.workers[0].storage_profile,
            count=workers_count)

    nfs_count = len(entity_status.nodes.nfs)
    if nfs_count == 0:
        nfs = rde_2_0_0.Nfs(sizing_class=None, storage_profile=None,
                            count=0)
    else:
        nfs = rde_2_0_0.Nfs(
            sizing_class=entity_status.nodes.nfs[0].sizing_class,  # noqa: E501
            storage_profile=entity_status.nodes.nfs[
                0].storage_profile, count=nfs_count)

    k8_distribution = rde_2_0_0.Distribution(
        template_name=entity_status.cloud_properties.distribution.template_name,  # noqa: E501
        template_revision=entity_status.cloud_properties.distribution.template_revision)  # noqa: E501

    network_settings = rde_2_0_0.Network(
        expose=entity_status.cloud_properties.exposed)

    settings = rde_2_0_0.Settings(
        ovdc_network=entity_status.cloud_properties.ovdc_network_name,
        ssh_key=entity_status.cloud_properties.ssh_key,
        rollback_on_failure=entity_status.cloud_properties.rollback_on_failure,  # noqa: E501
        network=network_settings)

    topology = rde_2_0_0.Topology(
        control_plane=control_plane,
        workers=workers,
        nfs=nfs)

    return rde_2_0_0.ClusterSpec(settings=settings,
                                 distribution=k8_distribution,
                                 topology=topology)


def load_rde_schema(schema_file: str) -> dict:
    try:
        schema_module = importlib.import_module(def_constants.DEF_SCHEMA_DIRECTORY)  # noqa: E501
        schema_file = pkg_resources.open_text(schema_module, schema_file)
        return json.load(schema_file)
    except (ImportError, ModuleNotFoundError, FileNotFoundError) as e:
        raise e
    finally:
        try:
            schema_file.close()
        except Exception:
            pass


def find_diff_fields(input_spec: dict, reference_spec: dict, exclude_fields: list = None) -> dict:  # noqa: E501
    if exclude_fields is None:
        exclude_fields = []
    input_dict = core_utils.flatten_dictionary(input_spec)
    reference_dict = core_utils.flatten_dictionary(reference_spec)
    exclude_key_set = set(exclude_fields)
    key_set_for_validation = set(input_dict.keys()) - exclude_key_set
    result = {}
    for key in key_set_for_validation:
        expected = reference_dict.get(key)
        actual = input_dict.get(key)
        if actual is not None and actual != expected:
            result[key] = {
                "expected": expected,
                "actual": actual
            }
    return result


def raise_error_if_unsupported_payload_version(payload_version: str):
    input_rde_version = def_constants.MAP_INPUT_PAYLOAD_VERSION_TO_RDE_VERSION.get(payload_version, def_constants.PayloadKey.UNKNOWN)  # noqa: E501
    runtime_rde_version = server_utils.get_rde_version_in_use()
    if input_rde_version == def_constants.PayloadKey.UNKNOWN or semantic_version.Version(input_rde_version) > semantic_version.Version(runtime_rde_version):  # noqa: E501
        raise exceptions.BadRequestError(f"Unsupported payload version: {payload_version}")  # noqa: E501


def convert_input_rde_to_runtime_rde_format(input_entity: dict):
    """Convert input entity to runtime rde format.

    :param AbstractNativeEntity input_entity: entity to be converted
    :return: Entity in runtime rde format
    :rtype: AbstractNativeEntity
    """
    payload_version = input_entity.get(def_constants.PayloadKey.PAYLOAD_VERSION)  # noqa: E501
    if payload_version:
        input_rde_version = def_constants.MAP_INPUT_PAYLOAD_VERSION_TO_RDE_VERSION[payload_version]  # noqa: E501
    else:
        input_rde_version = def_constants.RDEVersion.RDE_1_0_0.value
    runtime_rde_version = server_utils.get_rde_version_in_use()
    RuntimeNativeEntityClass: Type[AbstractNativeEntity] = rde_factory.get_rde_model(runtime_rde_version)  # noqa: E501
    InputNativeEntityClass: Type[AbstractNativeEntity] = rde_factory.get_rde_model(input_rde_version)  # noqa: E501
    input_rde: AbstractNativeEntity = InputNativeEntityClass.from_dict(input_entity)  # noqa: E501
    return RuntimeNativeEntityClass.from_native_entity(input_rde)


def convert_runtime_rde_to_input_rde_version_format(runtime_rde: AbstractNativeEntity, input_rde_version):  # noqa: E501
    InputNativeEntityClass: Type[AbstractNativeEntity] = rde_factory.get_rde_model(input_rde_version)  # noqa: E501
    output_entity = InputNativeEntityClass.from_native_entity(runtime_rde)
    return output_entity
