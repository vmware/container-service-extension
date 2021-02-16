import semantic_version

from container_service_extension.rde.validators.validator_rde_1_x import Validator1X  # noqa: E501
from container_service_extension.rde.validators.validator_rde_2_x import Validator2X  # noqa: E501


def get_validator(rde_version_in_use):
    """Get the right instance of input validator.

    Factory method to return the Validator based on the RDE version in use.
    :param rde_version_in_use (str)

    :rtype validator (container_service_extension.rde.validators.abstract_validator.AbstractValidator)  # noqa: E501
    """
    rde_version: semantic_version.Version = semantic_version.Version(
        rde_version_in_use)  # noqa: E501
    if rde_version.major == 1:
        return Validator1X()
    elif rde_version.major == 2:
        return Validator2X()


