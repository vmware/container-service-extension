#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.PksInfo import PksInfo
from container_service_extension.PvdcResourcePoolPathInfo import PvdcResourcePoolPathInfo
from container_service_extension.Uaac import Uaac


class CseCache(object):
    """
    An immutable class acting as an in-memory cache for Container Service Extention(CSE)
    """
    __slots__ = ["orgs","pks_accounts","pvdcs","pvdc_table", "pks_info_table", "org_pks_table"]

    def __init__(self, orgs, pks_accounts, pvdcs):
        """
        Constructor for CseCache cache
        :param orgs: array of dicts, each representing organization information in CSE PKS config
        :param pks_accounts: array of dicts, each representing PKS account information in CSE PKS config
        :param pvdcs: array of dicts, each representing Pvdc information in CSE PKS config
        """
        super(CseCache, self).__setattr__("orgs", orgs)
        super(CseCache, self).__setattr__("pks_accounts", pks_accounts)
        super(CseCache, self).__setattr__("pvdcs", pvdcs)
        pks_info_table = self.__load_pks_accounts(pks_accounts)
        pvdc_table = self.__load_pvdc_info(pvdcs)
        org_pks_table = self.__load_org_pks_accounts(orgs, pks_info_table)
        super(CseCache,self).__setattr__("pvdc_table",pvdc_table)
        super(CseCache, self).__setattr__("pks_info_table", pks_info_table)
        super(CseCache, self).__setattr__("org_pks_table", org_pks_table)



    def __setattr__(self, key, value):
        """
        Overridden method to customize the meaning of attribute access.
        Called when an attribute assignment is attempted.
        """
        msg = "'%s' has no attribute %s" % (self.__class__,
                                            key)
        raise AttributeError(msg)

    def get_pvdc_info(self, pvdc_id):
        """ Returns an immutable PvdcResourcePoolPathInfo object which has details of pvdc
        associated with this identifier. Details include datacenter name, cluster name and
        sub resource pool path for this provider vDC.

        :param pvdc_id: UUID of the provider vDC
        :return: PvdcResourcePoolPathInfo object
        """
        return self.pvdc_table[pvdc_id]


    def get_pks_account_details(self, org_name, vc_name):
        """Returns an immutable PksInfo object which has details of PKS account associated
        with the given organization and vCenter name.

        :param org_name: name of organization.
        :param vc_name: name of associated vCenter.
        :return: PksInfo object.
        """
        return self.org_pks_table[(org_name,vc_name)]


    def __load_pks_accounts(self, pks_accounts):
        """Construct a dict to access PKS account information (account name, host, port, uaac and vc name)
        based on its account name, from the pks information obtained from configuration.

        :param dict pks_accounts: array of dict, each representing PKS information in CSE PKS config.
        :return: dict of PKS information where key is the PKS account name and value is PksInfo object.

        :rtype: dict
        """
        pks = {}
        for account in pks_accounts:
            uaac = Uaac(account['uaac']['port'],
                        account['uaac']['secret'],
                        account['uaac']['username'])
            pks_info = PksInfo(account['name'],
                               account['host'],
                               account['port'],
                               uaac,
                               account['vc'])
            pks[account['name']] = pks_info

        return pks

    def __load_org_pks_accounts(self, orgs, pks_accounts):
        """Construct a dict to access PKS account information (account name, host, port, uaac and vc name)
        associated with each organization per vCenter based on the organization name and associated vCenter name.

        :param dict orgs: array of dict, each representing organization and its associated PKS accounts.
        :param dict pks_accounts: array of dict, each representing PKS information in CSE PKS config.
        :return: dict of PKS information where key is the PKS account name and value is PksInfo object.

        :rtype: dict
        """
        org_pks_association = {}
        for org in orgs:
            org_name = org['name']
            for account_name in org['pks_accounts']:
                associated_pks_account = pks_accounts[account_name]
                org_pks_association[(org_name, associated_pks_account.vc)] = associated_pks_account

        return org_pks_association

    def __load_pvdc_info(self, pvdcs_list):
        """Construct a dict to access pvdc information (datacenter, cluser and resourcepool path)
         based on its identifier, from the pvdc information obtained from PKS configuration.

        :param dict pvdcs_list: array of dict, each representing Pvdc information in CSE PKS config
        :return: dict of pvdc information where key is the pvdc identifier and value is PvdcResourcePoolPathInfo object.

        :rtype: dict
        """
        pvdc_table ={}
        for pvdc in self.pvdcs:
            from container_service_extension.utils import get_pvdc_id_by_name
            pvdc_id = get_pvdc_id_by_name(pvdc['name'], pvdc['vc'])
            from container_service_extension.utils import get_datacenter_cluster_rp_path
            datacenter, cluster, rp = get_datacenter_cluster_rp_path(pvdc['rp_paths'])
            pvdc_rp_info = PvdcResourcePoolPathInfo(pvdc['name'], pvdc['vc'], datacenter,cluster,rp)
            pvdc_table[str(pvdc_id)] = pvdc_rp_info

        return pvdc_table