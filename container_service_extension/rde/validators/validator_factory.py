import semantic_version

from container_service_extension.rde.validators.abstract_validator import AbstractValidator  # noqa: E501
from container_service_extension.rde.validators.validator_rde_1_x import Validator_1_0_0  # noqa: E501
from container_service_extension.rde.validators.validator_rde_2_x import Validator_2_0_0  # noqa: E501


def get_validator(rde_version_supported_api_handler: str) -> AbstractValidator:
    """Get the right instance of input validator.

    Factory method to return the Validator based on the RDE version in use.
    :param str rde_version_supported_api_handler: version of rde for the api handler
    :rtype validator (container_service_extension.rde.validators.abstract_validator.AbstractValidator)  # noqa: E501
    """
    rde_version: semantic_version.Version = semantic_version.Version(rde_version_supported_api_handler)  # noqa: E501
    if rde_version.major == 1:
        return Validator_1_0_0()
    elif rde_version.major == 2:
        return Validator_2_0_0()
