#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from collections import namedtuple
from container_service_extension.utils import get_datacenter_cluster_rp_path
from container_service_extension.utils import get_pvdc_id_by_name


class PksCache(object):
    """
    An immutable class acting as an in-memory cache for Container Service Extention(CSE) PKS.
    """
    __slots__ = ["orgs","pks_accounts","pvdcs","pvdc_table", "pks_info_table", "org_pks_table", "pks_service_accounts_per_vc_info_table"]

    def __init__(self, orgs, pks_accounts, pvdcs):
        """
        Constructor for PksCache cache
        :param orgs: array of dicts, each representing organization information in CSE PKS config
        :param pks_accounts: array of dicts, each representing PKS account information in CSE PKS config
        :param pvdcs: array of dicts, each representing Pvdc information in CSE PKS config
        """
        super().__setattr__("orgs", orgs)
        super().__setattr__("pks_accounts", pks_accounts)
        super().__setattr__("pvdcs", pvdcs)
        pks_info_table = self.__load_pks_accounts(pks_accounts)
        pvdc_table = self.__load_pvdc_info(pvdcs)
        if orgs[0]['name'] == 'None':
            pks_service_accounts_per_vc_info_table = self.__load_pks_service_accounts_per_vc(orgs, pks_info_table)
            super().__setattr__("pks_service_accounts_per_vc_info_table",
                                              pks_service_accounts_per_vc_info_table)
            super().__setattr__("org_pks_table", {})
        else:
            org_pks_table = self.__load_pks_service_accounts_per_org_per_vc(orgs, pks_info_table)
            super().__setattr__("org_pks_table", org_pks_table)
            super().__setattr__("pks_service_accounts_per_vc_info_table",
                                              {})
        super().__setattr__("pvdc_table", pvdc_table)
        super().__setattr__("pks_info_table", pks_info_table)




    def __setattr__(self, key, value):
        """
        Overridden method to customize the meaning of attribute access.
        Called when an attribute assignment is attempted.
        """
        msg = f"{self.class} has no attribute {key}"

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
        if len(self.org_pks_table) == 0:
            return self.pks_service_accounts_per_vc_info_table[vc_name]
        return self.org_pks_table[(org_name, vc_name)]


    def __load_pks_accounts(self, pks_accounts):
        """Construct a dict to access PKS account information (account name, host, port, uaac and vc name)
        based on its account name, from the pks information obtained from configuration.

        :param list pks_accounts: array of dict, each representing PKS information in CSE PKS config.
        :return: dict of PKS information where key is the PKS account name and value is PksInfo object.

        :rtype: dict
        """
        pks = dict()
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

    def __load_pks_service_accounts_per_vc(self, orgs, pks_accounts):
        """Construct a dict to access PKS account information (account name, host, port, uaac and vc name)
       per vCenter based on the associated vCenter name.

        :param list orgs: array of dict, each representing organization and its associated PKS accounts.
        :param dict pks_accounts: dict of pks account name(key) and PKS information(value) in CSE PKS config.
        :return: dict of PKS information where key is the vCenter name and value is PksInfo object.

        :rtype: dict
        """
        if orgs[0]['name'] == 'None':
            pks_service_accounts_per_vc_info_table = {}
            for account in pks_accounts.values():
                pks_service_accounts_per_vc_info_table[account.vc] = account
            return pks_service_accounts_per_vc_info_table



    def __load_pks_service_accounts_per_org_per_vc(self, orgs, pks_accounts):
        """Construct a dict to access PKS account information (account name, host, port, uaac and vc name)
        associated with each organization per vCenter based on the organization name and associated vCenter name.

        :param list orgs: array of dict, each representing organization and its associated PKS accounts.
        :param dict pks_accounts: dict of pks account name(key) and PKS information(value) in CSE PKS config.
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

        :param list pvdcs_list: array of dict, each representing Pvdc information in CSE PKS config
        :return: dict of pvdc information where key is the pvdc identifier and value is PvdcResourcePoolPathInfo object.

        :rtype: dict
        """
        pvdc_table ={}
        for pvdc in self.pvdcs:
            pvdc_id = get_pvdc_id_by_name(pvdc['name'], pvdc['vc'])
            datacenter, cluster, rp = get_datacenter_cluster_rp_path(pvdc['rp_paths'])
            pvdc_rp_info = PvdcResourcePoolPathInfo(pvdc['name'], pvdc['vc'], datacenter,cluster,rp)
            pvdc_table[str(pvdc_id)] = pvdc_rp_info

        return pvdc_table

class PksInfo(namedtuple("PksInfo", 'name, host, port, uaac, vc')):
    """
    Immutable class representing PKS account information.
    """
    def __str__(self):
        return "class:{c}, name: {name}, host: {host}, port : {port}," \
               " uaac : {uaac}, vc : {vc}".format(c=PksInfo.__name__,
                                                  name= self.name,
                                                  host= self.host,
                                                  port= self.port,
                                                  uaac = self.uaac,
                                                  vc = self.vc)

class PvdcResourcePoolPathInfo(namedtuple("PvdcResourcePoolPathInfo", 'name, vc, datacenter, cluster, rp_path')):
    """
    Immutable class representing Provider vDC related information for PKS setup.
    """
    def __str__(self):
        return "class:{c}, name : {name}, vc : {vc}, datacenter: {datacenter}, cluster : {cluster}," \
               " rp_path : {rp_path}".format(c=PvdcResourcePoolPathInfo.__name__,
                                             name = self.name,
                                             vc = self.vc,
                                             datacenter= self.datacenter,
                                             cluster= self.cluster,
                                             rp_path= self.rp_path)

class Uaac(namedtuple("Uaac", 'port, secret, username')):
    """
    Immutable class representing information on UAAC from PKS configuration
    """
    def __str__(self):
        return "class:{c}, port : {port}," \
               " secret : {secret}, username : {username}".format(c=Uaac.__name__,
                                                  port= self.port,
                                                  secret = self.secret,
                                                  username = self.username)