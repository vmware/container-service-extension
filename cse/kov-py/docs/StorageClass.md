# StorageClass

## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **str** | the name of the storage class | 
**datastore** | **str** | the name of the datastore to create the volume in | 
**cache_reservation** | **int** | Flash read cache reservation | [optional] 
**disk_stripes** | **int** | Number of disk stripes per object | [optional] 
**force_provisioning** | **bool** | Force provisioning | [optional] 
**host_failures_to_tolerate** | **int** | Number of failures to tolerate | [optional] 
**iops_limit** | **int** | IOPS limit for object | [optional] 
**object_space_reservation** | **int** | Object space reservation | [optional] 

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


