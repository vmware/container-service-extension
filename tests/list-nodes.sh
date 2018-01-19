#!/usr/bin/env bash

vcd cse cluster list

for i in `seq 1 3`;
do
  echo cluster$i
  vcd cse node list cluster$i
done
