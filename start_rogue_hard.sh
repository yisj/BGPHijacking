#!/bin/bash
echo "Killing any existing rogue AS"
sudo python run.py --node R6 --cmd "pkill -f --signal 9 [z]ebra-R6"
sudo python run.py --node R6 --cmd "pkill -f --signal 9 [b]gpd-R6"
echo "Starting rogue AS (hard)"
sudo python run.py --node R6 --cmd "/usr/lib/frr/zebra -f conf/zebra-R6.conf -d -i /tmp/zebra-R6.pid > logs/R6-zebra-stdout"
sudo python run.py --node R6 --cmd "/usr/lib/frr/bgpd -f conf/bgpd-R6-hard.conf -d -i /tmp/bgpd-R6.pid > logs/R6-bgpd-hard-stdout"