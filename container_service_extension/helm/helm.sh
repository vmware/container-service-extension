###### This script setups helm and the example chart repository for usage, after this you don't really 
## need the vcd cli helm stuff, but if you want to use it its works the same
### only run this if you want to add tiller to a cluster that doesn't have it

## for mac os and linux right now
## easier if you install helm yourself

i=$1

if [ "$i" == '-i' ]
then
	cd $(mktemp -d)

	curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get > get_helm.sh

	chmod 700 get_helm.sh

	./get_helm.sh
	# clean up unneccesary files

fi

# for helm to use to find your cluster

export KUBECONFIG=~/kubeconfig.yml

## creates tiller server on kubernetes cluster

helm init

##allow deployment of charts

kubectl create clusterrolebinding permissive-binding --clusterrole=cluster-admin --user=admin --user=kubelet --group=system:serviceaccounts

## its ready

helm repo update
