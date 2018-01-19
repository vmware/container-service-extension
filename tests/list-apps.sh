#!/usr/bin/env bash

for i in `seq 1 3`;
do
  vcd cse cluster config cluster$i > ~/.kube/config
  kubectl get node
  kubectl get pod --namespace sock-shop --output wide
done
