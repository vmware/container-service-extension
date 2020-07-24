# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from enum import Enum
from enum import unique

from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
import container_service_extension.exceptions as excptn

# Defined Entity Framework related constants
DEF_CSE_VENDOR = 'cse'
DEF_VMWARE_VENDOR = 'vmware'
DEF_VMWARE_INTERFACE_NSS = 'k8s'
DEF_VMWARE_INTERFACE_VERSION = '1.0.0'
DEF_VMWARE_INTERFACE_NAME = 'Kubernetes'
DEF_TKG_ENTITY_TYPE_NSS = 'tkgcluster'
DEF_TKG_ENTITY_TYPE_VERSION = '1.0.0'
DEF_INTERFACE_ID_PREFIX = 'urn:vcloud:interface'
DEF_NATIVE_ENTITY_TYPE_NSS = 'nativeCluster'
DEF_NATIVE_ENTITY_TYPE_VERSION = '1.0.0'
DEF_NATIVE_ENTITY_TYPE_NAME = 'nativeClusterEntityType'
DEF_ENTITY_TYPE_ID_PREFIX = 'urn:vcloud:type'
DEF_API_MIN_VERSION = 35.0
DEF_SCHEMA_DIRECTORY = 'cse_def_schema'
DEF_ENTITY_TYPE_SCHEMA_FILE = 'schema.json'
V35_END_POINT_DISCRIMINATOR = 'internal'
DEF_ERROR_MESSAGE_KEY = 'message'
DEF_RESOLVED_STATE = 'RESOLVED'
TKG_ENTITY_TYPE_NSS = 'tkgcluster'
TKG_ENTITY_TYPE_VERSION = '1.0.0'


@unique
class DefKey(str, Enum):
    INTERFACE_VENDOR = 'interface_vendor'
    INTERFACE_NSS = 'interface_nss'
    INTERFACE_VERSION = 'interface_version'
    INTERFACE_NAME = 'interface_name'
    ENTITY_TYPE_VENDOR = 'entity_type_vendor'
    ENTITY_TYPE_NAME = 'entity_type_name'
    ENTITY_TYPE_NSS = 'entity_type_nss'
    ENTITY_TYPE_VERSION = 'entity_type_version'
    ENTITY_TYPE_SCHEMA_VERSION = 'schema_version'


MAP_API_VERSION_TO_KEYS = {
    35.0: {
        DefKey.INTERFACE_VENDOR: DEF_VMWARE_VENDOR,
        DefKey.INTERFACE_NSS: DEF_VMWARE_INTERFACE_NSS,
        DefKey.INTERFACE_VERSION: DEF_VMWARE_INTERFACE_VERSION,
        DefKey.INTERFACE_NAME: DEF_VMWARE_INTERFACE_NAME,
        DefKey.ENTITY_TYPE_VENDOR: DEF_CSE_VENDOR,
        DefKey.ENTITY_TYPE_NSS: DEF_NATIVE_ENTITY_TYPE_NSS,
        DefKey.ENTITY_TYPE_VERSION: DEF_NATIVE_ENTITY_TYPE_VERSION,
        DefKey.ENTITY_TYPE_NAME: DEF_NATIVE_ENTITY_TYPE_NAME,
        DefKey.ENTITY_TYPE_SCHEMA_VERSION: 'api_v35',
    }
}


class ClusterEntityFilterKey(Enum):
    """Keys to filter cluster entities in CSE (or) vCD.

    Below Keys are commonly used filters. An entity can be filtered by any of
    its properties.

    Usage examples:
    ..api/cse/internal/clusters?entity.kind=native
    ..api/cse/internal/clusters?entity.metadata.org_name=org1
    ..cloudapi/1.0.0/entities?filter=entity.metadata.org_name==org1
    """

    # TODO(DEF) CLI can leverage this enum for the filter implementation.
    CLUSTER_NAME = 'name'
    ORG_NAME = 'entity.metadata.org_name'
    OVDC_NAME = 'entity.metadata.ovdc_name'
    KIND = 'entity.kind'
    K8_DISTRIBUTION = 'entity.spec.k8_distribution.template_name'
    STATE = 'state'
    PHASE = 'entity.status.phase'


class ClusterEntityKind(Enum):
    NATIVE = 'native'
    TKG = 'TanzuKubernetesCluster'
    TANZU_PLUS = 'TKG+'


def raise_error_if_def_not_supported(cloudapi_client: CloudApiClient):
    """Raise DefNotSupportedException if defined entities are not supported.

    :param cloudapi_client CloudApiClient
    """
    if float(cloudapi_client.get_api_version()) < DEF_API_MIN_VERSION:
        raise excptn.DefNotSupportedException("Defined entity framework is not"
                                              " supported for {cloudapi_client.get_api_version()}")  # noqa: E501


def get_registered_def_interface():
    """Fetch the native cluster interface loaded during server startup."""
    from container_service_extension.service import Service
    return Service().get_kubernetes_interface()


def get_registered_def_entity_type():
    """Fetch the native cluster entity type loaded during server startup."""
    from container_service_extension.service import Service
    return Service().get_native_cluster_entity_type()


def generate_interface_id(vendor, nss, version):
    """Generate defined entity interface id.

    By no means, id generation in this method, guarantees the actual
    entity type registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{DEF_INTERFACE_ID_PREFIX}:{vendor}:{nss}:{version}"


def generate_entity_type_id(vendor, nss, version):
    """Generate defined entity type id.

    By no means, id generation in this method, guarantees the actual
    interface registration with vCD.

    :param vendor (str)
    :param nss (str)
    :param version (str)

    :rtype str
    """
    return f"{DEF_ENTITY_TYPE_ID_PREFIX}:{vendor}:{nss}:{version}"
