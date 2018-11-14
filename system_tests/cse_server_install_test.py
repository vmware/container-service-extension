# VMware vCloud Director Python SDK
# Copyright (c) 2018 VMware, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from container_service_extension.system_test_framework.base_install_test \
    import BaseServerInstallTestCase
from container_service_extension.system_test_framework.environment \
    import developerModeAware


class CSEServerInstallationTest(BaseServerInstallTestCase):
    """Test CSE server installation."""

    # All tests in this module should be run as System Administrator
    _client = None

    def test_0000_setup(self):
        """."""
        pass

    @developerModeAware
    def test_9998_teardown(self):
        pass

    def test_9999_cleanup(self):
        """Release all resources held by this object for testing purposes."""
        if CSEServerInstallationTest._client is not None:
            CSEServerInstallationTest._client.logout()
