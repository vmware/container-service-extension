# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple

from container_service_extension.common.constants.server_constants import PKS_CLUSTER_DOMAIN_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import PKS_COMPUTE_PROFILE_KEY # noqa: E501
from container_service_extension.common.constants.server_constants import PKS_PLANS_KEY  # noqa: E501
from container_service_extension.common.utils.pyvcloud_utils import get_pvdc_id_from_pvdc_name # noqa: E501


class PksCache(object):
    """Immutable in-memory cache for CSE PKS.

    An immutable class acting as an in-memory cache for
    Container Service Extention(CSE) PKS.
    """

    __slots__ = [
        "orgs_have_exclusive_pks_account",
        # mapping of org name -> names of all pks accounts assigned to the org
        "orgs_to_pks_account_mapper",
        # mapping of pks server name -> pks server details
        "pks_servers_table",
        # mapping of vc -> nsxt server details
        "vc_to_nsxt_server_mapper",
        # mapping of pvdc id -> PvdcInfo objects
        "pvdc_info_table",
        # mapping of pks account name -> PksAccountInfo objects
        "pks_account_info_table",
        # mapping of vc name -> PksAccountInfo objects
        "vc_to_pks_info_mapper",
        # mapping of (vc name, org name) -> PksAccountInfo objects
        "vc_org_to_pks_info_mapper"
    ]

    def __init__(self, pks_servers, pks_accounts, pvdcs, orgs, nsxt_servers):
        """Initialize PksCache object.

        :param list pks_servers: list of dicts, each dict representing a PKS
            server. Details include host, port, uaac_port, data_center,
            clusters etc.
        :param list pks_accounts: list of dicts, each dict representing a PKS
            account. Details include username, secret and the PKS server to
            which is this account belongs to.
        :param list pvdcs: list of dicts, each dict representing a Pvdc.
            Details include name, backing pks server name, cluster name.
        :param list orgs: list of dicts, each dict representing an org.
            Details include org name and pks accounts allocated for the org.
        :param list nsxt_servers: list of dicts, each representing a nsxt
            server. Details include associated pks server name, host, user,
            password, configuration details of pks ip blocks etc.
        """
        orgs_to_pks_account_mapper = {}
        for org in orgs:
            orgs_to_pks_account_mapper[org['name']] = org['pks_accounts']
        super().__setattr__("orgs_to_pks_account_mapper",
                            orgs_to_pks_account_mapper)

        pks_servers_table = {}
        for pks_server in pks_servers:
            pks_servers_table[pks_server['name']] = pks_server
        super().__setattr__("pks_servers_table", pks_servers_table)

        vc_to_nsxt_server_mapper = {}
        for nsxt_server in nsxt_servers:
            pks_server = pks_servers_table[nsxt_server['pks_api_server']]
            vc_to_nsxt_server_mapper[pks_server['vc']] = nsxt_server
        super().__setattr__("vc_to_nsxt_server_mapper",
                            vc_to_nsxt_server_mapper)

        pvdc_info_table = self._construct_pvdc_info_table(pvdcs)
        super().__setattr__("pvdc_info_table", pvdc_info_table)

        pks_account_info_table = self._construct_pks_account_info_table(
            pks_accounts)
        super().__setattr__("pks_account_info_table", pks_account_info_table)

        vc_to_pks_info_mapper = {}
        vc_org_to_pks_info_mapper = {}
        if orgs:
            super().__setattr__("orgs_have_exclusive_pks_account", True)
            vc_org_to_pks_info_mapper = \
                self._construct_vc_org_to_pks_info_mapper()
        else:
            super().__setattr__("orgs_have_exclusive_pks_account", False)
            vc_to_pks_info_mapper = \
                self._construct_vc_to_pks_info_mapper()

        super().__setattr__("vc_to_pks_info_mapper", vc_to_pks_info_mapper)
        super().__setattr__("vc_org_to_pks_info_mapper",
                            vc_org_to_pks_info_mapper)

    def __setattr__(self, key, value):
        """Overridden method to customize the meaning of attribute access.

        Called when an attribute assignment is attempted.
        """
        msg = f"Attributes of {self.__class__} cannot be updated."

        raise AttributeError(msg)

    def __delattr__(self, *args):
        """Overridden method to customize the meaning of attribute access.

        Called when an attribute deletion is attempted.
        """
        msg = f"Attributes of {self.__class__} cannot be deleted"

        raise AttributeError(msg)

    def do_orgs_have_exclusive_pks_account(self):
        """Determine if orgs has been setup with exclusive PKS account.

        :return: True, if orgs in the setup have dedicated PKS accounts to
            talk to the PKS server backing them else False.

        :rtype: bool
        """
        return self.orgs_have_exclusive_pks_account

    def get_pvdc_info(self, pvdc_id):
        """Return an immutable PvdcInfo object.

        :param str pvdc_id: UUID of the provider vDC

        :return: PvdcInfo object
        """
        return self.pvdc_info_table.get(pvdc_id)

    def get_nsxt_info(self, vc):
        """Return a dict containing NSXT info.

        :param str vc: name of vCenter

        :return: dict containing NSXT info

        :rtype: dict
        """
        return self.vc_to_nsxt_server_mapper.get(vc)

    def get_pks_account_info(self, org_name, vc_name):
        """Return an immutable PksAccountInfo object.

        PksAccountInfo object has details of PKS account associated with
            the given organization and vCenter name.

        :param str org_name: name of organization.
        :param str vc_name: name of associated vCenter.

        :return: PksAccountInfo object.
        """
        if self.do_orgs_have_exclusive_pks_account():
            return self.vc_org_to_pks_info_mapper.get((org_name, vc_name))
        else:
            return self.vc_to_pks_info_mapper.get(vc_name)

    def get_exclusive_pks_accounts_info_for_org(self, org_name):
        """Return all pks accounts associated with an org.

        This method returns an empty list if the system is not configured to
        have PKS accounts dedicated at per org basis.

        :param str org_name: name of organization, whose associated PKS
            accounts are to be fetched.

        :return: list of PksAccountInfo object.

        :rtype: list
        """
        pks_account_infos = []
        if org_name in self.orgs_to_pks_account_mapper:
            pks_account_names_for_org = \
                self.orgs_to_pks_account_mapper[org_name]
            pks_account_infos = [
                self.pks_account_info_table[account_name]
                for account_name in pks_account_names_for_org
            ]
        return pks_account_infos

    def get_all_pks_account_info_in_system(self):
        """Return list of all PKS accounts in the entire system.

        :return: list of PksAccountInfo objects

        :rtype: list
        """
        return self.pks_account_info_table.values()

    @staticmethod
    def get_pks_keys():
        """Get relevant PKS keys.

        :return: Set of pks keys

        :rtype: set
        """
        keys = set(PksAccountInfo._fields)
        keys.remove('credentials')
        [keys.add(field) for field in PvdcInfo._fields]
        keys.add(PKS_PLANS_KEY)
        keys.add(PKS_COMPUTE_PROFILE_KEY)
        keys.add(PKS_CLUSTER_DOMAIN_KEY)
        return keys

    def _construct_pvdc_info_table(self, pvdcs):
        """Construct a dict to access pvdc information.

        This dict provides Pvdc information (datacenter, cluster
        and resource pool path) based on its identifier, from the pvdc
        information obtained from PKS configuration.

        :return: dict of pvdc information where key is the pvdc identifier and
        value is PvdcInfo object.

        :rtype: dict
        """
        pvdc_info_table = {}
        for pvdc in pvdcs:
            pvdc_name = pvdc['name']
            cluster = pvdc['cluster']
            pks_server_name = pvdc['pks_api_server']

            pks_server = self.pks_servers_table.get(pks_server_name)
            vc = pks_server['vc']
            datacenter = pks_server['datacenter']
            cpi = pks_server['cpi']

            pvdc_info = PvdcInfo(pvdc_name, vc, datacenter, cluster, cpi)

            pvdc_id = get_pvdc_id_from_pvdc_name(pvdc_name, vc)
            pvdc_info_table[str(pvdc_id)] = pvdc_info

        return pvdc_info_table

    def _construct_pks_account_info_table(self, pks_accounts):
        """Construct a dict to access PKS account information.

        This dict provides PKS account information (account
        name, host, port, uaac and vc name) based on its account name,
        from the pks information obtained from configuration.

        :param list pks_accounts: list of dictionaires, where each dict
            represents a PKS account. Details include name, username, secret
            and the PKS server which owns the account.

        :return: dict of PKS information where key is the PKS account
        name and value is PksAccountInfo object.

        :rtype: dict
        """
        pks_account_info_table = {}
        for pks_account in pks_accounts:
            pks_account_name = pks_account['name']
            credentials = Credentials(pks_account['username'],
                                      pks_account['secret'])

            pks_server_name = pks_account['pks_api_server']
            pks_server = self.pks_servers_table.get(pks_server_name)

            pks_proxy = '' \
                if 'proxy' not in pks_server else pks_server['proxy']

            pks_info = PksAccountInfo(pks_account_name,
                                      pks_server['host'],
                                      pks_server['port'],
                                      pks_server['verify'],
                                      pks_server['uaac_port'],
                                      credentials,
                                      pks_server['vc'],
                                      pks_proxy)

            pks_account_info_table[pks_account_name] = pks_info

        return pks_account_info_table

    def _construct_vc_to_pks_info_mapper(self):
        """Construct a dict to access PKS account information per vc.

        This dict provides PKS account information (account,
        name, host, port, uaac_port, credentials and vc name) per vCenter based
        on the associated vCenter name.

        :return: dict of PKS information where key is the vCenter name and
        value is PksAccountInfo object.

        :rtype: dict
        """
        vc_to_pks_info_mapper = {}
        for pks_info in self.pks_account_info_table.values():
            vc_to_pks_info_mapper[pks_info.vc] = pks_info
        return vc_to_pks_info_mapper

    def _construct_vc_org_to_pks_info_mapper(self):
        """Construct a dict to access PKS account information per org per vc.

        This dict provides PKS account information (account name, host,
        port, uaac_port, credentials and vc name) associated with each
        organization per vCenter based on the organization name and associated
        vCenter name.

        :return: dict of PKS information where key is a tuple of org name
        and vc name and value is PksAccountInfo object.

        :rtype: dict
        """
        vc_org_to_pks_info_mapper = {}
        for org_name, account_names in self.orgs_to_pks_account_mapper.items():
            for account_name in account_names:
                pks_info = self.pks_account_info_table[account_name]
                vc_org_to_pks_info_mapper[(org_name, pks_info.vc)] = pks_info
            return vc_org_to_pks_info_mapper


class PksAccountInfo(namedtuple("PksAccountInfo", "account_name, host, port, "
                                "verify, uaac_port, credentials, vc, proxy")):
    """Immutable class representing PKS account information."""

    def __str__(self):
        return "class:{c}, name: {name}, host: {host}, port: {port}, " \
               "verify: {verify}, uaac_port : {uaac_port}, "\
               "credentials : {credentials}, vc : {vc}, proxy : {proxy}"\
            .format(c=PksAccountInfo.__name__,
                    name=self.account_name,
                    host=self.host,
                    port=self.port,
                    verify=self.verify,
                    uaac_port=self.uaac_port,
                    credentials=self.credentials,
                    vc=self.vc, proxy=self.proxy)


class PvdcInfo(namedtuple("PvdcInfo",
                          "pvdc_name, vc, datacenter, cluster, cpi")):
    """Immutable class representing Provider vDC related info for PKS setup."""

    def __str__(self):
        return "class:{c}, pvdc_name : {name}, vc : {vc}," \
               " datacenter: {datacenter}, cluster : {cluster}," \
               " cpi : {cpi}".format(c=PvdcInfo.__name__,
                                     name=self.pvdc_name, vc=self.vc,
                                     datacenter=self.datacenter,
                                     cluster=self.cluster, cpi=self.cpi)


class Credentials(namedtuple("Credentials", "username, secret")):
    """Immutable class representing a pair of username, secret."""

    def __str__(self):
        return "class:{c}, username : {username}, secret : {secret}, "\
            .format(c=Credentials.__name__, username=self.username,
                    secret=self.secret)
