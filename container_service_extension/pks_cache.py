#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple

from container_service_extension.utils import get_pvdc_id_by_name

PKS_PLANS = 'pks_plans'
PKS_COMPUTE_PROFILE = 'pks_compute_profile_name'

class PksCache(object):
    """Immutable in-memory cache for CSE PKS.

    An immutable class acting as an in-memory cache for
    Container Service Extention(CSE) PKS.
    """

    __slots__ = ["orgs", "pks_accounts", "pvdcs",
                 "pvdc_table", "pks_info_table",
                 "pks_service_accounts_per_org_per_vc_info_table",
                 "pks_service_accounts_per_vc_info_table"]

    def __init__(self, orgs, pks_accounts, pvdcs):
        """Initialize PksCache cache.

        :param orgs: array of dicts, each representing organization information
        in CSE PKS config
        :param pks_accounts: array of dicts, each representing PKS account
        information in CSE PKS config
        :param pvdcs: array of dicts, each representing Pvdc information in
        CSE PKS config
        """
        super().__setattr__("orgs", orgs)
        super().__setattr__("pks_accounts", pks_accounts)
        super().__setattr__("pvdcs", pvdcs)
        pks_info_table = self._construct_pks_accounts()
        pvdc_table = self._construct_pvdc_info()
        super().__setattr__("pvdc_table", pvdc_table)
        super().__setattr__("pks_info_table", pks_info_table)
        if orgs is not None and orgs[0]['name'] == 'None':
            pks_service_accounts_per_vc_info_table = \
                self._construct_pks_service_accounts_per_vc()
            super().__setattr__("pks_service_accounts_per_vc_info_table",
                                pks_service_accounts_per_vc_info_table)
            super().__setattr__(
                "pks_service_accounts_per_org_per_vc_info_table", {})
        else:
            pks_service_accounts_per_org_per_vc_info_table = self.\
                _construct_pks_service_accounts_per_org_per_vc()
            super().__setattr__(
                "pks_service_accounts_per_org_per_vc_info_table",
                pks_service_accounts_per_org_per_vc_info_table)
            super().__setattr__("pks_service_accounts_per_vc_info_table", {})

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

    def get_pvdc_info(self, pvdc_id):
        """Return an immutable PvdcResourcePoolPathInfo object.

        PvdcResourcePoolPathInfo object has details of pvdc associated
        with this identifier. Details include datacenter name, cluster
        name and sub resource pool path for this provider vDC.

        :param str pvdc_id: UUID of the provider vDC
        :return: PvdcResourcePoolPathInfo object
        """
        return self.pvdc_table.get(pvdc_id)

    def get_pks_account_details(self, org_name, vc_name):
        """Return an immutable PksInfo object.

        PksInfo object has details of PKS account associated with
        the given organization and vCenter name.

        :param str org_name: name of organization.
        :param str vc_name: name of associated vCenter.
        :return: PksInfo object.
        """
        if len(self.pks_service_accounts_per_org_per_vc_info_table) == 0:
            return self.pks_service_accounts_per_vc_info_table[vc_name]
        return self.pks_service_accounts_per_org_per_vc_info_table.get(
            (org_name, vc_name))

    def get_all_pks_accounts_for_org(self, org_name):
        """Return all pks accounts associated with this org.

        Each PksInfo object has details of PKS account associated with
        the given organization.

        :param str org_name: name of organization.
        :return: list of PksInfo object.

        :rtype: list
        """
        pks_account_names_for_org = []
        for org in self.orgs:
            if org['name'] == org_name:
                pks_account_names_for_org = org['pks_accounts']
        pks_accounts = [self.pks_info_table[name]
                        for name in pks_account_names_for_org]
        return pks_accounts

    def get_pks_keys(self):
        """ Get relevant PKS keys

        :return: Set of pks keys

        :rtype: set
        """
        keys = set(PksInfo._fields)
        keys.remove('credentials')
        [keys.add(field) for field in PvdcInfo._fields]
        keys.add(PKS_PLANS)
        keys.add(PKS_COMPUTE_PROFILE)
        return keys


    def _construct_pks_accounts(self):
        """Construct a dict to access PKS account information.

        This dict provides PKS account information (account
        name, host, port, uaac and vc name) based on its account name,
        from the pks information obtained from configuration.

        :return: dict of PKS information where key is the PKS account
        name and value is PksInfo object.

        :rtype: dict
        """
        pks = dict()
        for account in self.pks_accounts:
            credentials = Credentials(account['uaac']['username'],
                                      account['uaac']['secret'])
            pks_proxy = '' \
                if 'proxy' not in account else account['proxy']
            pks_info = PksInfo(account['name'],
                               account['host'],
                               account['port'],
                               account['uaac']['port'],
                               credentials,
                               account['vc'],
                               pks_proxy)
            pks_account_name = account['name']
            pks[pks_account_name] = pks_info

        return pks

    def _construct_pks_service_accounts_per_vc(self):
        """Construct a dict to access PKS account information per vc.

        This dict provides PKS account information (account,
        name, host, port, uaac_port, credentials and vc name) per vCenter based on the
        associated vCenter name.

        :return: dict of PKS information where key is the vCenter name and
        value is PksInfo object.

        :rtype: dict
        """
        if self.orgs[0]['name'] == 'None':
            pks_service_accounts_per_vc_info_table = {}
            for account in self.pks_info_table.values():
                pks_service_accounts_per_vc_info_table[account.vc] = account
            return pks_service_accounts_per_vc_info_table

    def _construct_pks_service_accounts_per_org_per_vc(self):
        """Construct a dict to access PKS account information per org per vc.

        This dict provides PKS account information (account name, host,
        port, uaac_port, credentials and vc name) associated with each organization per vCenter
        based on the organization name and associated vCenter name.

        :return: dict of PKS information where key is a tuple of org name
        and vc name and value is PksInfo object.

        :rtype: dict
        """
        org_pks_association = {}
        for org in self.orgs:
            org_name = org['name']
            for account_name in org['pks_accounts']:
                associated_pks_account = self.pks_info_table[account_name]
                org_pks_association[(org_name, associated_pks_account.vc)] = \
                    associated_pks_account
            return org_pks_association

    def _construct_pvdc_info(self):
        """Construct a dict to access pvdc information.

        This dict provides Pvdc information (datacenter, cluster
        and resource pool path) based on its identifier, from the pvdc
        information obtained from PKS configuration.

        :return: dict of pvdc information where key is the pvdc identifier and
        value is PvdcResourcePoolPathInfo object.

        :rtype: dict
        """
        pvdc_table = {}
        for pvdc in self.pvdcs:
            pvdc_id = get_pvdc_id_by_name(pvdc['name'], pvdc['vc'])
            datacenter, cluster = pvdc['datacenter'], pvdc['cluster']
            cpi = pvdc['cpi']
            pvdc_rp_info = PvdcInfo(pvdc['name'],
                                    pvdc['vc'],
                                    datacenter, cluster, cpi)
            pvdc_table[str(pvdc_id)] = pvdc_rp_info

        return pvdc_table


class PksInfo(namedtuple("PksInfo", 'account_name, host, port, uaac_port, '
                                    'credentials, vc, proxy')):
    """Immutable class representing PKS account information."""

    def __str__(self):
        return "class:{c}, name: {name}, host: {host}, port : {port}, " \
               "uaac_port : {uaac_port}, credentials : {credentials}, " \
               "vc : {vc}, proxy : {proxy}"\
            .format(c=PksInfo.__name__,
                    name=self.account_name,
                    host=self.host,
                    port=self.port,
                    uaac_port=self.uaac_port,
                    credentials=self.credentials,
                    vc=self.vc, proxy=self.proxy)


class PvdcInfo(namedtuple("PvdcResourcePoolPathInfo",
                                          'pvdc_name, vc, datacenter, cluster,'
                                          ' cpi')):
    """Immutable class representing Provider vDC related info for PKS setup."""

    def __str__(self):
        return "class:{c}, pvdc_name : {name}, vc : {vc}," \
               " datacenter: {datacenter}, cluster : {cluster}," \
               " cpi : {cpi}".format(c=PvdcInfo.__name__,
                                     name=self.pvdc_name, vc=self.vc,
                                     datacenter=self.datacenter,
                                     cluster=self.cluster, cpi=self.cpi)


class Credentials(namedtuple("Credentials", 'username, secret')):
    """Immutable class representing info on Credentials from PKS configuration."""

    def __str__(self):
        return "class:{c}, username : {username}, secret : {secret}, "\
            .format(c=Credentials.__name__, username=self.username,
                    secret=self.secret)
