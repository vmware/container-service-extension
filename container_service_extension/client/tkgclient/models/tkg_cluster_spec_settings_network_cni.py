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


class TkgClusterSpecSettingsNetworkCni(object):
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
        'name': 'str'
    }

    attribute_map = {
        'name': 'name'
    }

    def __init__(self, name=None):  # noqa: E501
        """TkgClusterSpecSettingsNetworkCni - a model defined in Swagger"""  # noqa: E501

        self._name = None
        self.discriminator = None

        if name is not None:
            self.name = name

    @property
    def name(self):
        """Gets the name of this TkgClusterSpecSettingsNetworkCni.  # noqa: E501

        Specifies the CNI to use. Currently only \"calico\" is supported. Any other value is not valid.   # noqa: E501

        :return: The name of this TkgClusterSpecSettingsNetworkCni.  # noqa: E501
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name):
        """Sets the name of this TkgClusterSpecSettingsNetworkCni.

        Specifies the CNI to use. Currently only \"calico\" is supported. Any other value is not valid.   # noqa: E501

        :param name: The name of this TkgClusterSpecSettingsNetworkCni.  # noqa: E501
        :type: str
        """

        self._name = name

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

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, TkgClusterSpecSettingsNetworkCni):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
