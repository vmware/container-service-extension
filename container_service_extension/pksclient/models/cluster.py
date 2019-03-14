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

from container_service_extension.pksclient.models.cluster_parameters import ClusterParameters  # noqa: F401,E501


class Cluster(object):
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
        'plan_name': 'str',
        'last_action': 'str',
        'last_action_state': 'str',
        'last_action_description': 'str',
        'uuid': 'str',
        'kubernetes_master_ips': 'list[str]',
        'network_profile_name': 'str',
        'compute_profile_name': 'str',
        'parameters': 'ClusterParameters'
    }

    attribute_map = {
        'name': 'name',
        'plan_name': 'plan_name',
        'last_action': 'last_action',
        'last_action_state': 'last_action_state',
        'last_action_description': 'last_action_description',
        'uuid': 'uuid',
        'kubernetes_master_ips': 'kubernetes_master_ips',
        'network_profile_name': 'network_profile_name',
        'compute_profile_name': 'compute_profile_name',
        'parameters': 'parameters'
    }

    def __init__(self, name=None, plan_name=None, last_action=None, last_action_state=None, last_action_description=None, uuid=None, kubernetes_master_ips=None, network_profile_name=None, compute_profile_name=None, parameters=None):  # noqa: E501
        """Cluster - a model defined in Swagger"""  # noqa: E501

        self._name = None
        self._plan_name = None
        self._last_action = None
        self._last_action_state = None
        self._last_action_description = None
        self._uuid = None
        self._kubernetes_master_ips = None
        self._network_profile_name = None
        self._compute_profile_name = None
        self._parameters = None
        self.discriminator = None

        self.name = name
        self.plan_name = plan_name
        if last_action is not None:
            self.last_action = last_action
        if last_action_state is not None:
            self.last_action_state = last_action_state
        if last_action_description is not None:
            self.last_action_description = last_action_description
        self.uuid = uuid
        if kubernetes_master_ips is not None:
            self.kubernetes_master_ips = kubernetes_master_ips
        if network_profile_name is not None:
            self.network_profile_name = network_profile_name
        if compute_profile_name is not None:
            self.compute_profile_name = compute_profile_name
        if parameters is not None:
            self.parameters = parameters

    @property
    def name(self):
        """Gets the name of this Cluster.  # noqa: E501


        :return: The name of this Cluster.  # noqa: E501
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name):
        """Sets the name of this Cluster.


        :param name: The name of this Cluster.  # noqa: E501
        :type: str
        """
        if name is None:
            raise ValueError("Invalid value for `name`, must not be `None`")  # noqa: E501

        self._name = name

    @property
    def plan_name(self):
        """Gets the plan_name of this Cluster.  # noqa: E501


        :return: The plan_name of this Cluster.  # noqa: E501
        :rtype: str
        """
        return self._plan_name

    @plan_name.setter
    def plan_name(self, plan_name):
        """Sets the plan_name of this Cluster.


        :param plan_name: The plan_name of this Cluster.  # noqa: E501
        :type: str
        """
        if plan_name is None:
            raise ValueError("Invalid value for `plan_name`, must not be `None`")  # noqa: E501

        self._plan_name = plan_name

    @property
    def last_action(self):
        """Gets the last_action of this Cluster.  # noqa: E501


        :return: The last_action of this Cluster.  # noqa: E501
        :rtype: str
        """
        return self._last_action

    @last_action.setter
    def last_action(self, last_action):
        """Sets the last_action of this Cluster.


        :param last_action: The last_action of this Cluster.  # noqa: E501
        :type: str
        """

        self._last_action = last_action

    @property
    def last_action_state(self):
        """Gets the last_action_state of this Cluster.  # noqa: E501


        :return: The last_action_state of this Cluster.  # noqa: E501
        :rtype: str
        """
        return self._last_action_state

    @last_action_state.setter
    def last_action_state(self, last_action_state):
        """Sets the last_action_state of this Cluster.


        :param last_action_state: The last_action_state of this Cluster.  # noqa: E501
        :type: str
        """
        allowed_values = ["in progress", "succeeded", "failed"]  # noqa: E501
        if last_action_state not in allowed_values:
            raise ValueError(
                "Invalid value for `last_action_state` ({0}), must be one of {1}"  # noqa: E501
                .format(last_action_state, allowed_values)
            )

        self._last_action_state = last_action_state

    @property
    def last_action_description(self):
        """Gets the last_action_description of this Cluster.  # noqa: E501


        :return: The last_action_description of this Cluster.  # noqa: E501
        :rtype: str
        """
        return self._last_action_description

    @last_action_description.setter
    def last_action_description(self, last_action_description):
        """Sets the last_action_description of this Cluster.


        :param last_action_description: The last_action_description of this Cluster.  # noqa: E501
        :type: str
        """

        self._last_action_description = last_action_description

    @property
    def uuid(self):
        """Gets the uuid of this Cluster.  # noqa: E501


        :return: The uuid of this Cluster.  # noqa: E501
        :rtype: str
        """
        return self._uuid

    @uuid.setter
    def uuid(self, uuid):
        """Sets the uuid of this Cluster.


        :param uuid: The uuid of this Cluster.  # noqa: E501
        :type: str
        """
        if uuid is None:
            raise ValueError("Invalid value for `uuid`, must not be `None`")  # noqa: E501

        self._uuid = uuid

    @property
    def kubernetes_master_ips(self):
        """Gets the kubernetes_master_ips of this Cluster.  # noqa: E501


        :return: The kubernetes_master_ips of this Cluster.  # noqa: E501
        :rtype: list[str]
        """
        return self._kubernetes_master_ips

    @kubernetes_master_ips.setter
    def kubernetes_master_ips(self, kubernetes_master_ips):
        """Sets the kubernetes_master_ips of this Cluster.


        :param kubernetes_master_ips: The kubernetes_master_ips of this Cluster.  # noqa: E501
        :type: list[str]
        """

        self._kubernetes_master_ips = kubernetes_master_ips

    @property
    def network_profile_name(self):
        """Gets the network_profile_name of this Cluster.  # noqa: E501


        :return: The network_profile_name of this Cluster.  # noqa: E501
        :rtype: str
        """
        return self._network_profile_name

    @network_profile_name.setter
    def network_profile_name(self, network_profile_name):
        """Sets the network_profile_name of this Cluster.


        :param network_profile_name: The network_profile_name of this Cluster.  # noqa: E501
        :type: str
        """

        self._network_profile_name = network_profile_name

    @property
    def compute_profile_name(self):
        """Gets the compute_profile_name of this Cluster.  # noqa: E501


        :return: The compute_profile_name of this Cluster.  # noqa: E501
        :rtype: str
        """
        return self._compute_profile_name

    @compute_profile_name.setter
    def compute_profile_name(self, compute_profile_name):
        """Sets the compute_profile_name of this Cluster.


        :param compute_profile_name: The compute_profile_name of this Cluster.  # noqa: E501
        :type: str
        """

        self._compute_profile_name = compute_profile_name

    @property
    def parameters(self):
        """Gets the parameters of this Cluster.  # noqa: E501


        :return: The parameters of this Cluster.  # noqa: E501
        :rtype: ClusterParameters
        """
        return self._parameters

    @parameters.setter
    def parameters(self, parameters):
        """Sets the parameters of this Cluster.


        :param parameters: The parameters of this Cluster.  # noqa: E501
        :type: ClusterParameters
        """

        self._parameters = parameters

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
        if not isinstance(other, Cluster):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
