#!/bin/sh

router_id=$1
input_ports=$2
outputs=$3
timer_values=$4


if [ -f ./router.py ];
then
  echo "Calling router.py with values: ${router_id}, ${input_ports}, ${outputs}, ${timer_values}"
  gnome-terminal --wait -- python3 ./router.py "${router_id}" "${input_ports}" "${outputs}" "${timer_values}"
else
  echo "router.py not in directory"
fi

