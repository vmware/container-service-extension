#!/usr/bin/env bash

for i in `seq 1 3`;
do
  vcd cse cluster config cluster$i > ~/.kube/config
  kubectl get node
  kubectl create namespace sock-shop
  kubectl apply -n sock-shop -f "https://github.com/microservices-demo/microservices-demo/blob/master/deploy/kubernetes/complete-demo.yaml?raw=true"
  kubectl get pod --namespace sock-shop --output wide
done
