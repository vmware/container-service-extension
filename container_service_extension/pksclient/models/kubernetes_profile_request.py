# coding: utf-8

"""
    PKS

    PKS API  # noqa: E501

    OpenAPI spec version: 1.1.0
    
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""


import pprint
import re  # noqa: F401

import six


class KubernetesProfileRequest(object):
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
        'description': 'str',
        'customizations': 'list[KubernetesComponentCustomization]',
        'experimental_customizations': 'list[KubernetesComponentCustomization]'
    }

    attribute_map = {
        'name': 'name',
        'description': 'description',
        'customizations': 'customizations',
        'experimental_customizations': 'experimental_customizations'
    }

    def __init__(self, name=None, description=None, customizations=None, experimental_customizations=None):  # noqa: E501
        """KubernetesProfileRequest - a model defined in Swagger"""  # noqa: E501

        self._name = None
        self._description = None
        self._customizations = None
        self._experimental_customizations = None
        self.discriminator = None

        self.name = name
        if description is not None:
            self.description = description
        if customizations is not None:
            self.customizations = customizations
        if experimental_customizations is not None:
            self.experimental_customizations = experimental_customizations

    @property
    def name(self):
        """Gets the name of this KubernetesProfileRequest.  # noqa: E501


        :return: The name of this KubernetesProfileRequest.  # noqa: E501
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name):
        """Sets the name of this KubernetesProfileRequest.


        :param name: The name of this KubernetesProfileRequest.  # noqa: E501
        :type: str
        """
        if name is None:
            raise ValueError("Invalid value for `name`, must not be `None`")  # noqa: E501
        if name is not None and len(name) > 200:
            raise ValueError("Invalid value for `name`, length must be less than or equal to `200`")  # noqa: E501

        self._name = name

    @property
    def description(self):
        """Gets the description of this KubernetesProfileRequest.  # noqa: E501


        :return: The description of this KubernetesProfileRequest.  # noqa: E501
        :rtype: str
        """
        return self._description

    @description.setter
    def description(self, description):
        """Sets the description of this KubernetesProfileRequest.


        :param description: The description of this KubernetesProfileRequest.  # noqa: E501
        :type: str
        """
        if description is not None and len(description) > 4000:
            raise ValueError("Invalid value for `description`, length must be less than or equal to `4000`")  # noqa: E501

        self._description = description

    @property
    def customizations(self):
        """Gets the customizations of this KubernetesProfileRequest.  # noqa: E501


        :return: The customizations of this KubernetesProfileRequest.  # noqa: E501
        :rtype: list[KubernetesComponentCustomization]
        """
        return self._customizations

    @customizations.setter
    def customizations(self, customizations):
        """Sets the customizations of this KubernetesProfileRequest.


        :param customizations: The customizations of this KubernetesProfileRequest.  # noqa: E501
        :type: list[KubernetesComponentCustomization]
        """

        self._customizations = customizations

    @property
    def experimental_customizations(self):
        """Gets the experimental_customizations of this KubernetesProfileRequest.  # noqa: E501


        :return: The experimental_customizations of this KubernetesProfileRequest.  # noqa: E501
        :rtype: list[KubernetesComponentCustomization]
        """
        return self._experimental_customizations

    @experimental_customizations.setter
    def experimental_customizations(self, experimental_customizations):
        """Sets the experimental_customizations of this KubernetesProfileRequest.


        :param experimental_customizations: The experimental_customizations of this KubernetesProfileRequest.  # noqa: E501
        :type: list[KubernetesComponentCustomization]
        """

        self._experimental_customizations = experimental_customizations

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
        if issubclass(KubernetesProfileRequest, dict):
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
        if not isinstance(other, KubernetesProfileRequest):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
