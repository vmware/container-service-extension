This wiki assumes that you followed the instructions for uploading the templates to vcloud and cse is registered as an extension on vcd-cli. 

****Creating a Cluster****

To create a cluster use vcd-cli first login to your vcd. While running the vcd cluster command make sure you are running the cse extension.

```
$ vcd login vcd.vmware.com au administrator –password ‘pas$word’

administrator logged in, org: 'System', vdc: ''

## creating the cluster
$ vcd cluster create c1

property    value
----------  ------------------------------------
cluster_id  75205cf6-ec27-4d2e-955f-bfbe6f2f2daf
name        c1

## check if cluster has been created
$ vcd cluster list 

IP master       name        nodes  vdc
--------------  --------  -------  ------
10.150.219.32   c2              2  au-vdc

## get the kubeconfig file from the cse extension
$ vcd cluster config c1 > ~/kubeconfig.yml

## set the environmental variable KUBECONFIG
$ export KUBECONFIG=~/kubeconfig.yml

```
Now your cluster is created and ready to use helm to create applications on your cluster.

****Installing Helm****

For all platforms you can install Helm from the installation scripts. Helm is a package manager that will allow you to install applications on your Kubernetes cluster. 

The installation script fetches the right binary for the os that you are working on.

```
$ curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get > get_helm.sh

  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  6164  100  6164    0     0  16607      0 --:--:-- --:--:-- --:--:-- 16569

$ chmod 700 get_helm.sh

$ ./get_helm.sh

Downloading https://kubernetes-helm.storage.googleapis.com/helm-v2.6.1-darwin-amd64.tar.gz
Preparing to install into /usr/local/bin
helm installed into /usr/local/bin/helm
Run 'helm init' to configure helm.
```
If you have brew you can instead run the command

```
$ brew install kubernetes-helm
```

****Installing Tiller****

Once you install helm, you have to configure tiller onto your cluster. First make sure the KUBECONFIG environmental variable is set.

```
$ export KUBECONFIG=~/kubeconfig.yml
```

Then you can install Tiller with the command helm init. If you want to set a different namespace for this pod make sure you set the corresponding flag. For basic installation though all you have to run is helm init.

```
$ helm init
$HELM_HOME has been configured at /Users/auppunda/.helm.

Tiller (the Helm server-side component) has been installed into your Kubernetes Cluster.
Happy Helming!

## check if tiller deployed
$ kubectl get po --namespace kube-system
NAME                                    READY     STATUS    RESTARTS   AGE
etcd-kubeclus-m1                        1/1       Running   0          7d
kube-apiserver-kubeclus-m1              1/1       Running   1          7d
kube-controller-manager-kubeclus-m1     1/1       Running   1          7d
kube-flannel-ds-sdmdw                   2/2       Running   0          7d
kube-flannel-ds-wl986                   2/2       Running   0          7d
kube-flannel-ds-ws1mn                   2/2       Running   0          7d
kube-proxy-h7w73                        1/1       Running   0          7d
kube-proxy-lz514                        1/1       Running   0          7d
kube-proxy-xfxfh                        1/1       Running   0          7d
kube-scheduler-kubeclus-m1              1/1       Running   1          7d
kubernetes-dashboard-3313488171-sg7cx   1/1       Running   0          7d
tiller-deploy-1651615695-x9xdf          1/1       Running   0          22m
```

The last item represents your tiller pod. This should be running.

****Launching an example chart****

Lets install Locust as our example chart. Locust is an open source load testing tool. There are many more charts that can be found in the charts repo under the incubator and stable folders. You can find this at the link https://github.com/kubernetes/charts . Now that you have tiller and helm installed this part is simple. 

```
## adds the repos into your helm repo for use with helm install
$ helm repo update 
Hang tight while we grab the latest from your chart repositories...
...Skip local chart repository
...Successfully got an update from the "incubator" chart repository
...Successfully got an update from the "stable" chart repository
Update Complete. ⎈ Happy Helming!⎈ 

## install command installs the chart that you specify
$ helm install -n locust-nymph --set master.config.target-host=http://127.0.0.1:9323 stable/locust

NAME:   locust-nymph
LAST DEPLOYED: Thu Sep  7 11:48:22 2017
NAMESPACE: default
STATUS: DEPLOYED

RESOURCES:
==> v1/ConfigMap
NAME                 DATA  AGE
locust-nymph-worker  1     3s

==> v1/Service
NAME                     CLUSTER-IP    EXTERNAL-IP  PORT(S)                                       AGE
locust-nymph-master-svc  10.102.38.82  <nodes>      8089:32165/TCP,5557:30983/TCP,5558:30516/TCP  3s

==> v1beta1/Deployment
NAME                 DESIRED  CURRENT  UP-TO-DATE  AVAILABLE  AGE
locust-nymph-master  1        1        1           0          3s
locust-nymph-worker  2        2        2           0          3s


NOTES:
locust installed!

Get the Locust URL to visit by running these commands in the same shell:
  export NODE_PORT=$(kubectl get svc -n default locust-nymph-master-svc -o jsonpath='{.spec.ports[?(@.name=="master-web")].nodePort}')
  export NODE_IP=$(kubectl get no -o jsonpath="{.items[0].status.addresses[0].address}")
  export LOCUST_URL=http://$NODE_IP:$NODE_PORT/

For more information on Distributed load testing on Kubernetes using Locust, visit:
https://cloud.google.com/solutions/distributed-load-testing-using-kubernetes

## verify that it installed into your cluster and is running
$ kubectl get po   
NAME                                                                    READY     STATUS    RESTARTS   AGE
locust-nymph-master-2838717832-vqrqw                 1/1       Running              0                 6m
locust-nymph-worker-3052503607-71szb                 1/1       Running              0                 6m
locust-nymph-worker-3052503607-cf5r3                 1/1       Running              0                 6m
```

****Deploying your helm app****

The main thing for getting charts up and running is following the instructions helm prints when it creates the chart.

```
## to launch locust
$ export NODE_PORT=$(kubectl get svc -n default locust-nymph-master-svc -o jsonpath='{.spec.ports[?(@.name=="master-web")].nodePort}')

$ export NODE_IP=$(kubectl get no -o jsonpath="{.items[0].status.addresses[0].address}")

$ export LOCUST_URL=http://$NODE_IP:$NODE_PORT/

## to get access to your locust app use the open command
$ open $LOCUST_URL
```

Once you open the url you are greeted with a page which allows you to use locust right away.

****Creating your own charts using helm****

In helm, creating charts is also a simple task. Lets create a chart called help. 

```
$ helm create help
creating help

$ cd help

$ ls 
Chart.yaml	charts	    templates	 values.yaml
```

chart.yaml  has info on your chart
charts contain all the charts your chart is dependent on
templates contain all your template files
values.yaml has all the default values for your templates

To add this to your helm repo of charts use the helm repo add command

```
$ helm repo add help
```
