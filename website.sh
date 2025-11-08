#!/bin/bash
# Copyright 2021-2024
# Georgia Tech
# All rights reserved
# Do not post or publish in any public or forbidden forums or websites

node=${1:-h5-1}
bold=`tput bold`
normal=`tput sgr0`

# For this assignment, we probe the AS1 service (11.0.1.1).
# When the hijack by AS6 is active, responses should come from the attacker web server.
while true; do
    out=`sudo python run.py --node $node --cmd "curl -s 11.0.1.1"`
    date=`date`
    echo $date -- $bold$out$normal
    sleep 1
done