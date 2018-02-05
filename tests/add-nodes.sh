#!/usr/bin/env bash

vcd cse cluster list

for i in `seq 1 3`;
do
  echo cluster$i
  vcd cse node create cluster$i --network $NETWORK --template $TEMPLATE --nodes 1
done
