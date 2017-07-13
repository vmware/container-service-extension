# ClusterUpdateConfig

## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **str** | the cluster name, should be valid for use in dns names | 
**min_nodes** | **int** | the minimum number of nodes that can be deployed | 
**max_nodes** | **int** | the minimum number of nodes that can be deployed | [optional] 
**no_of_masters** | **int** | the number of master nodes to create | [optional] [default to 1]
**storage_classes** | [**list[StorageClass]**](StorageClass.md) |  | [optional] 
**ops_username** | **str** |  | 
**ops_password** | **str** |  | 
**authorized_keys** | **list[str]** | the public keys that should get root ssh access to the nodes | [optional] 

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


