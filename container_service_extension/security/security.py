# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import re

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.thread_local_data as thread_local_data  # noqa: E501


class RedactingFilter(logging.Filter):
    """Filter class to redact sensitive infomarion in logs.

    This filter looks for certain sensitive keys and if a match is found, the
    value will be redacted. The value are expected to be strings. If they are
    dictionaries or iterables, resulting redaction will be partial. Normally
    the value for a sensitive key will be a plain string.
    """

    _SENSITIVE_KEYS = ['authorization',
                       'x-vcloud-authorization',
                       'x-vmware-vcloud-access-token',
                       'username',
                       'secret',
                       'password']

    _REDACTED_MSG = r"[REDACTED]"

    def __init__(self):
        """."""
        super(RedactingFilter, self).__init__()

        pattern_key = r""
        # concatenate all sensitive keys with | symbol
        for key in self._SENSITIVE_KEYS:
            pattern_key += key + r"|"
        # remove the last | symbol
        pattern_key = pattern_key[:-1]

        # The following pattern will match key-value pairs as follows
        # key: value
        # key: 'value'
        # 'key': value
        # 'key': 'value'
        # where key is one of the keys defined in the list of sensitive keys
        # and value will be accessible as group 1
        # Regex explanation :
        #   1. Look for a match with one of the keys
        #   2. Look for 0 or 1 instance of ' or "
        #   3. Look for a colon
        #   4. Look for 1 or more instances of space
        #   5. Look for 0 or more instances of [ or { <-- looking for starting
        #      token for a dict or list
        #   6. Look for 0 or 1 instance of '
        #   7. Put everything that is not ', space or } in a group,
        #      this group must be atleast of length 1.
        self._pattern = r"((" + pattern_key + r")(\"|')?:\s+[{\[]*'?)([^',}]+)"

    def filter(self, record):
        """Overridden filter method to redact log records.

        record.msg is always a string, record.args is the arg list from which
        the formatter will pick values if necessary and hence should be
        redacted too.

        :param logRecord record: logRecord object that needs redaction

        :returns: True, which forces the filter chain processing to continue.

        :rtype: boolean
        """
        record.msg = self.redact(record.msg)
        record.requestId = thread_local_data.get_thread_local_data(
            server_constants.ThreadLocalData.REQUEST_ID)  # noqa: E501
        if len(record.args) != 0:
            record.args = self.redact(record.args)
        return True

    def redact(self, obj):
        """Redact sensitive data in an object.

        The redaction algorithm will preserve dictionary structure. Iterables
        like list etc. will be converted to n-tuple. Everything else will be
        converted to string.

        :param object obj: the object which contains sensitive data to be
            redacted.

        :return: the redacted version of the object.

        :rtype: object
        """
        if obj is None:
            return obj

        is_iterable = True
        try:
            iter(theElement)
        except (NameError, TypeError):
            is_iterable = False

        if isinstance(obj, dict):
            result = {}
            for k in obj.keys():
                if str(k).lower() in self._SENSITIVE_KEYS:
                    result[k] = self._REDACTED_MSG
                else:
                    result[k] = self.redact(obj[k])
            return result
        elif is_iterable:
            return tuple(self.redact(item) for item in obj)
        else:
            msg_str = str(obj)
            redacted_msg = re.sub(pattern=self._pattern,
                                  string=msg_str,
                                  repl=r"\1" + self._REDACTED_MSG,
                                  flags=re.IGNORECASE)
            return redacted_msg


def _test_redaction_filter():
    logger = logging.getLogger("random1.2.3")
    logger.addFilter(RedactingFilter())
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.FileHandler('test.log'))

    base_str = "This is just a test string."

    # Case 1 : key : value
    dikt = {1: 2}
    msg = base_str + str(dikt)
    logger.debug(msg)

    # Case 2 : key : 'value'
    dikt = {1: '2'}
    msg = base_str + str(dikt)
    logger.debug(msg)

    # Case 3 : 'key' : value
    dikt1 = {'normal_key': 123}
    dikt2 = {'username': 345}
    msg = base_str + str(dikt1) + "," + str(dikt2)
    logger.debug(msg)

    # Case 4 : 'key' : 'value'
    dikt1 = {'normal_key': 123}
    dikt2 = {'username': 'super secret user name'}
    msg = base_str + str(dikt1) + "," + str(dikt2)
    logger.debug(msg)

    # Case 5 : Ignore case
    dikt1 = {'normal_key': 123}
    dikt2 = {'usERname': 'super secret user name'}
    msg = base_str + str(dikt1) + "," + str(dikt2)
    logger.debug(msg)

    # Case 6 : Multiple matches
    dikt1 = {'password': 'super secret password'}
    dikt2 = {'username': 'super secret user name'}
    msg = base_str + str(dikt1) + "," + str(dikt2)
    logger.debug(msg)

    # Case 7 : Empty value
    dikt1 = {'password': 'super secret password'}
    dikt2 = {'username': ''}
    # expected no redaction for empty value
    msg = base_str + str(dikt1) + "," + str(dikt2)
    logger.debug(msg)

    # Case 8 : Nested dictionaries with bad value
    dikt1 = {'normal_key': 'normal_value'}
    dikt2 = {'password': dikt1}
    # expected - improper redaction - since value is not string
    msg = base_str + str(dikt1) + "," + str(dikt2)
    logger.debug(msg)

    # Case 9 : dictionary with multiple sensitive keys
    dikt = {
        'password': 'super secret password',
        'normal_key': 'normal_value',
        'username': 'super secret username'
    }
    msg = base_str + str(dikt)
    logger.debug(msg)

    # Case 10 : Battle Royale
    dikt1 = {
        'Authorization': 'Base 64 encoded string',
        'PasswOrd': 'super secret password',
        'normal_key': ['', 'sshhh'],
        'username': '',
        'secret': 'shhh'
    }
    dikt2 = {
        'Authorization': 'Base 64 encoded string',
        'PasswOrd': 'super secret password',
        'normal_key': '',
        'username': '',
        'secret': dikt1
    }
    # expected - improper redaction - since value is not always string
    msg = base_str + str(dikt1) + "," + str(dikt2)
    logger.debug(msg)

    # Case 11 : Real world example
    # note : the secret is invalid but has the correct format
    msg = "ovdc metadata for cse-org-vdc-cse-org=>{'pks_plans': ['Plan 1'], " \
        "'host': 'api.pks.local', 'account_name': 'cse-org-service-account', "\
        "'uaac_port': '8443', 'cluster': 'kubo-az-1', 'datacenter': " \
        "'kubo-dc', 'pks_compute_profile_name': 'cp--c1f22cc3-6238-40ec-925" \
        "2-4162b7c5f1f8--cse-org-vdc', 'proxy': '10.161.67.157', 'port': " \
        "'9021', 'vc': 'vc1', 'cpi': 'b0f29ab638499e84db21', 'pvdc_name': " \
        "'vc1-TestbedCluster-20:37:43', 'username': 'admin', 'secret': " \
        "'S2syTXN6T2JTaV9EbkhzbmdRZVZJemVBaG9lMTFrMnU=', " \
        "'container_provider': 'pks'}"
    logger.debug(msg)


if __name__ == "__main__":
    _test_redaction_filter()
