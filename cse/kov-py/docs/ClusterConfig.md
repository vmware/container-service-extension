# ClusterConfig

## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **str** | the cluster name, should be valid for use in dns names | 
**min_nodes** | **int** | the minimum number of nodes that can be deployed | 
**max_nodes** | **int** | the minimum number of nodes that can be deployed | [optional] 
**no_of_masters** | **int** | the number of master nodes to create | [default to 1]
**leader_endpoint** | [**NetworkEndpoint**](NetworkEndpoint.md) | leader node network configuration | [optional] 
**storage_classes** | [**list[StorageClass]**](StorageClass.md) |  | [optional] 
**service_network** | **str** | the service network for the deployed nodes | [optional] 
**node_network** | **str** | the network used for node-to-node communication, | 
**network_provider** | **str** | the network provider of the cluster | [optional] [default to 'canal']
**datacenter** | **str** | the vsphere datacenter | 
**datastore** | **str** | the datastore for node | 
**vsphere_cluster** | **str** |  | 
**ops_username** | **str** |  | 
**ops_password** | **str** |  | 
**authorized_keys** | **list[str]** | the public keys that should get root ssh access to the nodes | [optional] 

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


