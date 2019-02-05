#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.PksInfo import PksInfo
from container_service_extension.PvdcResourcePoolPathInfo import PvdcResourcePoolPathInfo
from container_service_extension.Uaac import Uaac
from container_service_extension.utils import get_pvdc_id_by_name, get_datacenter_cluster_rp_path


class CseCache(object):
    """
    An immutable class acting as an in-memory cache for Container Service Extention(CSE)
    """
    __slots__ = ["orgs","pks_accounts","pvdcs","pvdc_table", "pks_info_table", "orgs_table"]

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
        # pks_info_table = self.__load_pks_accounts(pks_accounts)
        pvdc_table = self.__load_pvdc_info(pvdcs)
        # orgs_table = self.__load_org_pks_accounts(orgs, pks_info_table)
        super(CseCache,self).__setattr__("pvdc_table",pvdc_table)
        # super(CseCache, self).__setattr__("pks_info_table", pks_info_table)
        # super(CseCache, self).__setattr__("orgs_table", orgs_table)



    def __setattr__(self, key, value):
        """
        Overridden method to customize the meaning of attribute access.
        Called when an attribute assignment is attempted.
        """
        msg = "'%s' has no attribute %s" % (self.__class__,
                                            key)
        raise AttributeError(msg)

    def get_pvdc_info(self, pvdc_id):
        return self.pvdc_table[pvdc_id]


    # def get_pks_account_details(self, org_name, vc_name):
    #     list = self.org_pks_accounts_table[org_name]
    #     for account in list:
    #         if account.vc == vc_name:
    #             return account
    #
    # def __load_pks_accounts(self, pks_accounts_list):
    #     pks_information = {}
    #     for account in pks_accounts_list:
    #         uaac = Uaac(account['uaac']['port'],
    #                     account['uaac']['secret'],
    #                     account['uaac']['username'])
    #         pks_info = PksInfo(account['name'],
    #                            account['host'],
    #                            account['port'],
    #                            uaac,
    #                            account['vc'])
    #         pks_information[account['name']] = pks_info
    #
    #     return  pks_information
    #
    # def __load_org_pks_accounts(self, orgs_list, pks_info_list):
    #     org_pks_accounts = {}
    #     for org in self.orgs:
    #         key = org['name']
    #         values = []
    #         for account in org['pks_accounts']:
    #             values.append(pks_info_list[account])
    #             org_pks_accounts[key] = values
    #
    #     return org_pks_accounts

    def __load_pvdc_info(self, pvdcs_list):
        """Construct a dict to access pvdc information (datacenter, cluser and resourcepool path)
         based on its identifier, from the pvdc information obtained from PKS configuration.

        :param dict pvdcs_list: array of dict, each representing Pvdc information in CSE PKS config
        :return: dict of pvdc information where key is the pvdc identifier and value is PvdcResourcePoolPathInfo object.

        :rtype: dict
        """
        pvdc_table ={}
        for pvdc in self.pvdcs:
            pvdc_id = get_pvdc_id_by_name(pvdc['name'], pvdc['vc_name_in_vcd'])
            datacenter, cluster, rp = get_datacenter_cluster_rp_path(pvdc['rp_path'])
            pvdc_rp_info = PvdcResourcePoolPathInfo(pvdc['name'], pvdc['vc_name_in_vcd'], datacenter,cluster,rp)
            pvdc_table[str(pvdc_id)] = pvdc_rp_info

        return pvdc_table




