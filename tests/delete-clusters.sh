#!/usr/bin/env bash

for i in `seq 1 3`;
do
  vcd --no-wait cse cluster delete cluster$i --yes
done

watch vcd task list running
