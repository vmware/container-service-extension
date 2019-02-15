#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple

from container_service_extension.utils import get_datacenter_cluster_rp_path
from container_service_extension.utils import get_pvdc_id_by_name


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
        if orgs is not None and orgs[0]['name'] == 'None':
            pks_service_accounts_per_vc_info_table = \
                self._construct_pks_service_accounts_per_vc(pks_info_table)
            super().__setattr__("pks_service_accounts_per_vc_info_table",
                                pks_service_accounts_per_vc_info_table)
            super().__setattr__(
                "pks_service_accounts_per_org_per_vc_info_table", {})
        else:
            pks_service_accounts_per_org_per_vc_info_table = self.\
                _construct_pks_service_accounts_per_org_per_vc(pks_info_table)
            super().__setattr__(
                "pks_service_accounts_per_org_per_vc_info_table",
                pks_service_accounts_per_org_per_vc_info_table)
            super().__setattr__("pks_service_accounts_per_vc_info_table", {})
        super().__setattr__("pvdc_table", pvdc_table)
        super().__setattr__("pks_info_table", pks_info_table)

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
            uaac = Uaac(account['uaac']['port'],
                        account['uaac']['secret'],
                        account['uaac']['username'])
            pks_info = PksInfo(account['name'],
                               account['host'],
                               account['port'],
                               uaac,
                               account['vc'])
            pks_account_name = account['name']
            pks[pks_account_name] = pks_info

        return pks

    def _construct_pks_service_accounts_per_vc(self, pks_accounts):
        """Construct a dict to access PKS account information per vc.

        This dict provides PKS account information (account,
        name, host, port, uaac and vc name) per vCenter based on the
        associated vCenter name.

        :param dict pks_accounts: dict of pks account name(key) and PKS
        information(value) in CSE PKS config.
        :return: dict of PKS information where key is the vCenter name and
        value is PksInfo object.

        :rtype: dict
        """
        if self.orgs[0]['name'] == 'None':
            pks_service_accounts_per_vc_info_table = {}
            for account in pks_accounts.values():
                pks_service_accounts_per_vc_info_table[account.vc] = account
            return pks_service_accounts_per_vc_info_table

    def _construct_pks_service_accounts_per_org_per_vc(self, pks_accounts):
        """Construct a dict to access PKS account information per org per vc.

        This dict provides PKS account information (account name, host,
        port, uaac and vc name) associated with each organization per vCenter
        based on the organization name and associated vCenter name.

        :param dict pks_accounts: dict of pks account name(key) and PKS
        information(value) in CSE PKS config.
        :return: dict of PKS information where key is a tuple of org name
        and vc name and value is PksInfo object.

        :rtype: dict
        """
        org_pks_association = {}
        for org in self.orgs:
            org_name = org['name']
            for account_name in org['pks_accounts']:
                associated_pks_account = pks_accounts[account_name]
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
            datacenter, cluster, rp = \
                get_datacenter_cluster_rp_path(pvdc['rp_paths'])
            pvdc_rp_info = PvdcResourcePoolPathInfo(pvdc['name'],
                                                    pvdc['vc'],
                                                    datacenter, cluster, rp)
            pvdc_table[str(pvdc_id)] = pvdc_rp_info

        return pvdc_table


class PksInfo(namedtuple("PksInfo", 'name, host, port, uaac, vc')):
    """Immutable class representing PKS account information."""

    def __str__(self):
        return "class:{c}, name: {name}, host: {host}, port : {port}," \
               " uaac : {uaac}, vc : {vc}".format(c=PksInfo.__name__,
                                                  name=self.name,
                                                  host=self.host,
                                                  port=self.port,
                                                  uaac=self.uaac,
                                                  vc=self.vc)


class PvdcResourcePoolPathInfo(namedtuple("PvdcResourcePoolPathInfo",
                                          'name, vc, datacenter, cluster,'
                                          ' rp_path')):
    """Immutable class representing Provider vDC related info for PKS setup."""

    def __str__(self):
        return "class:{c}, name : {name}, vc : {vc}," \
               " datacenter: {datacenter}, cluster : {cluster}," \
               " rp_path : {rp_path}".format(c=PvdcResourcePoolPathInfo
                                             .__name__,
                                             name=self.name,
                                             vc=self.vc,
                                             datacenter=self.datacenter,
                                             cluster=self.cluster,
                                             rp_path=self.rp_path)


class Uaac(namedtuple("Uaac", 'port, secret, username')):
    """Immutable class representing info on UAAC from PKS configuration."""

    def __str__(self):
        return "class:{c}, port : {port}, secret : {secret}, username : " \
               "{username}".format(c=Uaac.__name__, port=self.port,
                                   secret=self.secret, username=self.username)
