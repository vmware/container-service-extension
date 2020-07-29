# coding: utf-8

"""
    TKG Kubernetes API

    This API provides to vCD tenants the means to provision (create and update) Tanzu Kubernetes Grid clusters. This is complementary to the defined-entity APIs:    GET /cloudapi/1.0.0/entities/urn:vcloud:entity:vmware.tkgcluster:1.0.0:{id} which allows to retrieve the clusters created by the API presented here. This is why you will not find here a GET operation for the corresponding entity.   # noqa: E501

    OpenAPI spec version: 1.0.0
    
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""

import pprint
import re  # noqa: F401

import six


class TkgClusterMetadata(object):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    """
    """
    Attributes:
      swagger_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    swagger_types = {
        'name': 'str',
        'placement_policy': 'str',
        'virtual_data_center_name': 'str',
        'resource_version': 'str'
    }

    attribute_map = {
        'name': 'name',
        'placement_policy': 'placementPolicy',
        'virtual_data_center_name': 'virtualDataCenterName',
        'resource_version': 'resourceVersion'
    }

    def __init__(self, name=None, placement_policy=None, virtual_data_center_name=None, resource_version=None):  # noqa: E501
        """TkgClusterMetadata - a model defined in Swagger"""  # noqa: E501
        self._name = None
        self._placement_policy = None
        self._virtual_data_center_name = None
        self._resource_version = None
        self.discriminator = None
        self.name = name
        self.placement_policy = placement_policy
        self.virtual_data_center_name = virtual_data_center_name
        if resource_version is not None:
            self.resource_version = resource_version

    @property
    def name(self):
        """Gets the name of this TkgClusterMetadata.  # noqa: E501

        Specifies the name of the cluster to create. Required during create, read-only after. It's a user-defined string that accepts alphanumeric characters and dashes,   # noqa: E501

        :return: The name of this TkgClusterMetadata.  # noqa: E501
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name):
        """Sets the name of this TkgClusterMetadata.

        Specifies the name of the cluster to create. Required during create, read-only after. It's a user-defined string that accepts alphanumeric characters and dashes,   # noqa: E501

        :param name: The name of this TkgClusterMetadata.  # noqa: E501
        :type: str
        """
        if name is None:
            raise ValueError("Invalid value for `name`, must not be `None`")  # noqa: E501

        self._name = name

    @property
    def placement_policy(self):
        """Gets the placement_policy of this TkgClusterMetadata.  # noqa: E501

        Targets where to place this cluster. Note that the placement policy also determines the range of valid values for storage class (see classes and defaultClass below) and virtual hardware settings (see VirtualMachineClass below). Required during create, read-only after.   # noqa: E501

        :return: The placement_policy of this TkgClusterMetadata.  # noqa: E501
        :rtype: str
        """
        return self._placement_policy

    @placement_policy.setter
    def placement_policy(self, placement_policy):
        """Sets the placement_policy of this TkgClusterMetadata.

        Targets where to place this cluster. Note that the placement policy also determines the range of valid values for storage class (see classes and defaultClass below) and virtual hardware settings (see VirtualMachineClass below). Required during create, read-only after.   # noqa: E501

        :param placement_policy: The placement_policy of this TkgClusterMetadata.  # noqa: E501
        :type: str
        """
        if placement_policy is None:
            raise ValueError("Invalid value for `placement_policy`, must not be `None`")  # noqa: E501

        self._placement_policy = placement_policy

    @property
    def virtual_data_center_name(self):
        """Gets the virtual_data_center_name of this TkgClusterMetadata.  # noqa: E501

        Cloud Director organization vDC where to place the cluster. Required during create, read-only after.   # noqa: E501

        :return: The virtual_data_center_name of this TkgClusterMetadata.  # noqa: E501
        :rtype: str
        """
        return self._virtual_data_center_name

    @virtual_data_center_name.setter
    def virtual_data_center_name(self, virtual_data_center_name):
        """Sets the virtual_data_center_name of this TkgClusterMetadata.

        Cloud Director organization vDC where to place the cluster. Required during create, read-only after.   # noqa: E501

        :param virtual_data_center_name: The virtual_data_center_name of this TkgClusterMetadata.  # noqa: E501
        :type: str
        """
        if virtual_data_center_name is None:
            raise ValueError("Invalid value for `virtual_data_center_name`, must not be `None`")  # noqa: E501

        self._virtual_data_center_name = virtual_data_center_name

    @property
    def resource_version(self):
        """Gets the resource_version of this TkgClusterMetadata.  # noqa: E501

        A value checked by the Supervisor Cluster to ensure that it matches the latest known state of the cluster.   # noqa: E501

        :return: The resource_version of this TkgClusterMetadata.  # noqa: E501
        :rtype: str
        """
        return self._resource_version

    @resource_version.setter
    def resource_version(self, resource_version):
        """Sets the resource_version of this TkgClusterMetadata.

        A value checked by the Supervisor Cluster to ensure that it matches the latest known state of the cluster.   # noqa: E501

        :param resource_version: The resource_version of this TkgClusterMetadata.  # noqa: E501
        :type: str
        """

        self._resource_version = resource_version

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value
        if issubclass(TkgClusterMetadata, dict):
            for key, value in self.items():
                result[key] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, TkgClusterMetadata):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
