# swagger_client.DefaultApi

All URIs are relative to *https://localhost*

Method | HTTP request | Description
------------- | ------------- | -------------
[**add_user**](DefaultApi.md#add_user) | **PUT** /clusters/{clustername}/users | adds a user to a cluster
[**create_cluster**](DefaultApi.md#create_cluster) | **POST** /clusters | creates a cluster
[**delete_cluster**](DefaultApi.md#delete_cluster) | **DELETE** /clusters/{name} | deletes a cluster
[**get_task**](DefaultApi.md#get_task) | **GET** /tasks/{taskid} | get the task for the given task id
[**get_user_config**](DefaultApi.md#get_user_config) | **GET** /clusters/{clustername}/users/{username}/config | retrieves the user kubeconfig
[**list_clusters**](DefaultApi.md#list_clusters) | **GET** /clusters | get a list of all clusters
[**list_task_i_ds**](DefaultApi.md#list_task_i_ds) | **GET** /tasks | get a list of task IDs
[**logs_cluster**](DefaultApi.md#logs_cluster) | **POST** /clusters/{name}/logs | fetches cluster logs
[**update_cluster**](DefaultApi.md#update_cluster) | **PUT** /clusters/{name} | updates a cluster


# **add_user**
> add_user(x_vc_username, x_vc_password, x_vc_endpoint, clustername, user, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)

adds a user to a cluster

adds a user to a cluster by generating certs for the user

### Example 
```python
from __future__ import print_statement
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.DefaultApi()
x_vc_username = 'x_vc_username_example' # str | Username for VC
x_vc_password = 'x_vc_password_example' # str | Password for VC
x_vc_endpoint = 'x_vc_endpoint_example' # str | VC endpoint
clustername = 'clustername_example' # str | the cluster name
user = 'user_example' # str | the user name to get the cluster config for
x_request_id = 'x_request_id_example' # str | A unique UUID for the request (optional)
x_vc_thumbprint = 'x_vc_thumbprint_example' # str | Thumbprint for VC (optional)

try: 
    # adds a user to a cluster
    api_instance.add_user(x_vc_username, x_vc_password, x_vc_endpoint, clustername, user, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)
except ApiException as e:
    print("Exception when calling DefaultApi->add_user: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **x_vc_username** | **str**| Username for VC | 
 **x_vc_password** | **str**| Password for VC | 
 **x_vc_endpoint** | **str**| VC endpoint | 
 **clustername** | **str**| the cluster name | 
 **user** | **str**| the user name to get the cluster config for | 
 **x_request_id** | **str**| A unique UUID for the request | [optional] 
 **x_vc_thumbprint** | **str**| Thumbprint for VC | [optional] 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **create_cluster**
> TaskId create_cluster(x_vc_username, x_vc_password, x_vc_endpoint, cluster_config, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)

creates a cluster

creates a cluster

### Example 
```python
from __future__ import print_statement
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.DefaultApi()
x_vc_username = 'x_vc_username_example' # str | Username for VC
x_vc_password = 'x_vc_password_example' # str | Password for VC
x_vc_endpoint = 'x_vc_endpoint_example' # str | VC endpoint
cluster_config = swagger_client.ClusterConfig() # ClusterConfig | the config of the cluster to be created
x_request_id = 'x_request_id_example' # str | A unique UUID for the request (optional)
x_vc_thumbprint = 'x_vc_thumbprint_example' # str | Thumbprint for VC (optional)

try: 
    # creates a cluster
    api_response = api_instance.create_cluster(x_vc_username, x_vc_password, x_vc_endpoint, cluster_config, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->create_cluster: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **x_vc_username** | **str**| Username for VC | 
 **x_vc_password** | **str**| Password for VC | 
 **x_vc_endpoint** | **str**| VC endpoint | 
 **cluster_config** | [**ClusterConfig**](ClusterConfig.md)| the config of the cluster to be created | 
 **x_request_id** | **str**| A unique UUID for the request | [optional] 
 **x_vc_thumbprint** | **str**| Thumbprint for VC | [optional] 

### Return type

[**TaskId**](TaskId.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_cluster**
> TaskId delete_cluster(x_vc_username, x_vc_password, x_vc_endpoint, name, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)

deletes a cluster

deletes a cluster with the given name

### Example 
```python
from __future__ import print_statement
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.DefaultApi()
x_vc_username = 'x_vc_username_example' # str | Username for VC
x_vc_password = 'x_vc_password_example' # str | Password for VC
x_vc_endpoint = 'x_vc_endpoint_example' # str | VC endpoint
name = 'name_example' # str | the cluster name to be deleted
x_request_id = 'x_request_id_example' # str | A unique UUID for the request (optional)
x_vc_thumbprint = 'x_vc_thumbprint_example' # str | Thumbprint for VC (optional)

try: 
    # deletes a cluster
    api_response = api_instance.delete_cluster(x_vc_username, x_vc_password, x_vc_endpoint, name, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->delete_cluster: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **x_vc_username** | **str**| Username for VC | 
 **x_vc_password** | **str**| Password for VC | 
 **x_vc_endpoint** | **str**| VC endpoint | 
 **name** | **str**| the cluster name to be deleted | 
 **x_request_id** | **str**| A unique UUID for the request | [optional] 
 **x_vc_thumbprint** | **str**| Thumbprint for VC | [optional] 

### Return type

[**TaskId**](TaskId.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_task**
> Task get_task(taskid, x_request_id=x_request_id)

get the task for the given task id

### Example 
```python
from __future__ import print_statement
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.DefaultApi()
taskid = 'taskid_example' # str | the id for a task
x_request_id = 'x_request_id_example' # str | A unique UUID for the request (optional)

try: 
    # get the task for the given task id
    api_response = api_instance.get_task(taskid, x_request_id=x_request_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->get_task: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **taskid** | **str**| the id for a task | 
 **x_request_id** | **str**| A unique UUID for the request | [optional] 

### Return type

[**Task**](Task.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_user_config**
> str get_user_config(clustername, username, x_request_id=x_request_id)

retrieves the user kubeconfig

retrieves the kubeconfig of the admin of the cluster

### Example 
```python
from __future__ import print_statement
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.DefaultApi()
clustername = 'clustername_example' # str | the cluster name
username = 'username_example' # str | the user name to get the cluster config for
x_request_id = 'x_request_id_example' # str | A unique UUID for the request (optional)

try: 
    # retrieves the user kubeconfig
    api_response = api_instance.get_user_config(clustername, username, x_request_id=x_request_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->get_user_config: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **clustername** | **str**| the cluster name | 
 **username** | **str**| the user name to get the cluster config for | 
 **x_request_id** | **str**| A unique UUID for the request | [optional] 

### Return type

**str**

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **list_clusters**
> list[Cluster] list_clusters(x_vc_username, x_vc_password, x_vc_endpoint, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)

get a list of all clusters

get a list of all clusters managed by the VCCS

### Example 
```python
from __future__ import print_statement
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.DefaultApi()
x_vc_username = 'x_vc_username_example' # str | Username for VC
x_vc_password = 'x_vc_password_example' # str | Password for VC
x_vc_endpoint = 'x_vc_endpoint_example' # str | VC endpoint
x_request_id = 'x_request_id_example' # str | A unique UUID for the request (optional)
x_vc_thumbprint = 'x_vc_thumbprint_example' # str | Thumbprint for VC (optional)

try: 
    # get a list of all clusters
    api_response = api_instance.list_clusters(x_vc_username, x_vc_password, x_vc_endpoint, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->list_clusters: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **x_vc_username** | **str**| Username for VC | 
 **x_vc_password** | **str**| Password for VC | 
 **x_vc_endpoint** | **str**| VC endpoint | 
 **x_request_id** | **str**| A unique UUID for the request | [optional] 
 **x_vc_thumbprint** | **str**| Thumbprint for VC | [optional] 

### Return type

[**list[Cluster]**](Cluster.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **list_task_i_ds**
> list[str] list_task_i_ds(x_request_id=x_request_id, limit=limit)

get a list of task IDs

get a list of IDs of tasks submitted to kovd

### Example 
```python
from __future__ import print_statement
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.DefaultApi()
x_request_id = 'x_request_id_example' # str | A unique UUID for the request (optional)
limit = 10 # int |  (optional) (default to 10)

try: 
    # get a list of task IDs
    api_response = api_instance.list_task_i_ds(x_request_id=x_request_id, limit=limit)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->list_task_i_ds: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **x_request_id** | **str**| A unique UUID for the request | [optional] 
 **limit** | **int**|  | [optional] [default to 10]

### Return type

**list[str]**

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **logs_cluster**
> TaskId logs_cluster(x_vc_username, x_vc_password, x_vc_endpoint, name, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)

fetches cluster logs

fetches cluster logs

### Example 
```python
from __future__ import print_statement
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.DefaultApi()
x_vc_username = 'x_vc_username_example' # str | Username for VC
x_vc_password = 'x_vc_password_example' # str | Password for VC
x_vc_endpoint = 'x_vc_endpoint_example' # str | VC endpoint
name = 'name_example' # str | the cluster name to be queried
x_request_id = 'x_request_id_example' # str | A unique UUID for the request (optional)
x_vc_thumbprint = 'x_vc_thumbprint_example' # str | Thumbprint for VC (optional)

try: 
    # fetches cluster logs
    api_response = api_instance.logs_cluster(x_vc_username, x_vc_password, x_vc_endpoint, name, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->logs_cluster: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **x_vc_username** | **str**| Username for VC | 
 **x_vc_password** | **str**| Password for VC | 
 **x_vc_endpoint** | **str**| VC endpoint | 
 **name** | **str**| the cluster name to be queried | 
 **x_request_id** | **str**| A unique UUID for the request | [optional] 
 **x_vc_thumbprint** | **str**| Thumbprint for VC | [optional] 

### Return type

[**TaskId**](TaskId.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **update_cluster**
> TaskId update_cluster(x_vc_username, x_vc_password, x_vc_endpoint, name, cluster_update_config, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)

updates a cluster

updates a cluster with the given update config

### Example 
```python
from __future__ import print_statement
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.DefaultApi()
x_vc_username = 'x_vc_username_example' # str | Username for VC
x_vc_password = 'x_vc_password_example' # str | Password for VC
x_vc_endpoint = 'x_vc_endpoint_example' # str | VC endpoint
name = 'name_example' # str | the cluster name to be updated
cluster_update_config = swagger_client.ClusterUpdateConfig() # ClusterUpdateConfig | the new config of the cluster to be updated
x_request_id = 'x_request_id_example' # str | A unique UUID for the request (optional)
x_vc_thumbprint = 'x_vc_thumbprint_example' # str | Thumbprint for VC (optional)

try: 
    # updates a cluster
    api_response = api_instance.update_cluster(x_vc_username, x_vc_password, x_vc_endpoint, name, cluster_update_config, x_request_id=x_request_id, x_vc_thumbprint=x_vc_thumbprint)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->update_cluster: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **x_vc_username** | **str**| Username for VC | 
 **x_vc_password** | **str**| Password for VC | 
 **x_vc_endpoint** | **str**| VC endpoint | 
 **name** | **str**| the cluster name to be updated | 
 **cluster_update_config** | [**ClusterUpdateConfig**](ClusterUpdateConfig.md)| the new config of the cluster to be updated | 
 **x_request_id** | **str**| A unique UUID for the request | [optional] 
 **x_vc_thumbprint** | **str**| Thumbprint for VC | [optional] 

### Return type

[**TaskId**](TaskId.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

