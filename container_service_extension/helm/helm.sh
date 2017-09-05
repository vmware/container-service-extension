###### This script setups helm and the example chart repository for usage, after this you don't really 
## need the vcd cli helm stuff, but if you want to use it its works the same
### only run this if you want to add tiller to a cluster that doesn't have it

i=$1

if [ $i == '-i' ]
then

	curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get > get_helm

	chmod 700 get_helm

	./get_helm
	# clean up unneccesary files
	rm get_helm

fi

# for helm to use to find your cluster

export KUBECONFIG=~/kubeconfig.yml

## creates tiller server on kubernetes cluster

helm init

##allow deployment of charts

kubectl create clusterrolebinding permissive-binding --clusterrole=cluster-admin --user=admin --user=kubelet --group=system:serviceaccounts

## its ready

helm repo update
