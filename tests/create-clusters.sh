#!/usr/bin/env bash

for i in `seq 1 3`;
do
  vcd --no-wait cse cluster create cluster$i --network $NETWORK --ssh-key ~/.ssh/id_rsa.pub --template $TEMPLATE
done

watch vcd task list running
