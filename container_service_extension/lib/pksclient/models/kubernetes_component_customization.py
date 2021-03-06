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


class KubernetesComponentCustomization(object):
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
        'component': 'str',
        'arguments': 'dict(str, str)',
        'file_arguments': 'dict(str, str)'
    }

    attribute_map = {
        'component': 'component',
        'arguments': 'arguments',
        'file_arguments': 'file-arguments'
    }

    def __init__(self, component=None, arguments=None, file_arguments=None):  # noqa: E501
        """KubernetesComponentCustomization - a model defined in Swagger"""  # noqa: E501

        self._component = None
        self._arguments = None
        self._file_arguments = None
        self.discriminator = None

        self.component = component
        if arguments is not None:
            self.arguments = arguments
        if file_arguments is not None:
            self.file_arguments = file_arguments

    @property
    def component(self):
        """Gets the component of this KubernetesComponentCustomization.  # noqa: E501


        :return: The component of this KubernetesComponentCustomization.  # noqa: E501
        :rtype: str
        """
        return self._component

    @component.setter
    def component(self, component):
        """Sets the component of this KubernetesComponentCustomization.


        :param component: The component of this KubernetesComponentCustomization.  # noqa: E501
        :type: str
        """
        if component is None:
            raise ValueError("Invalid value for `component`, must not be `None`")  # noqa: E501

        self._component = component

    @property
    def arguments(self):
        """Gets the arguments of this KubernetesComponentCustomization.  # noqa: E501


        :return: The arguments of this KubernetesComponentCustomization.  # noqa: E501
        :rtype: dict(str, str)
        """
        return self._arguments

    @arguments.setter
    def arguments(self, arguments):
        """Sets the arguments of this KubernetesComponentCustomization.


        :param arguments: The arguments of this KubernetesComponentCustomization.  # noqa: E501
        :type: dict(str, str)
        """

        self._arguments = arguments

    @property
    def file_arguments(self):
        """Gets the file_arguments of this KubernetesComponentCustomization.  # noqa: E501


        :return: The file_arguments of this KubernetesComponentCustomization.  # noqa: E501
        :rtype: dict(str, str)
        """
        return self._file_arguments

    @file_arguments.setter
    def file_arguments(self, file_arguments):
        """Sets the file_arguments of this KubernetesComponentCustomization.


        :param file_arguments: The file_arguments of this KubernetesComponentCustomization.  # noqa: E501
        :type: dict(str, str)
        """

        self._file_arguments = file_arguments

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
        if issubclass(KubernetesComponentCustomization, dict):
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
        if not isinstance(other, KubernetesComponentCustomization):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other