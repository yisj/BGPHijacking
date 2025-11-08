#!/usr/bin/env python
# Copyright 2021-2024
# Georgia Tech
# All rights reserved
# Do not post or publish in any public or forbidden forums or websites

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import Switch

from argparse import ArgumentParser
from time import sleep
import os
import termcolor as T

setLogLevel('info')

parser = ArgumentParser("Configure BGP network in Mininet (Figure 2 topology).")
parser.add_argument('--rogue', action="store_true", default=False)
parser.add_argument('--scriptfile', default=None)
parser.add_argument('--sleep', default=3, type=int)
args = parser.parse_args()

FLAGS_rogue_as = args.rogue
ROGUE_AS_NAME = 'R6'  # AS6 is the false origin (rogue)

def log(s, col="green"):
    print(T.colored(s, col))

class Router(Switch):
    """Container (namespace) for routing daemons."""
    ID = 0
    def __init__(self, name, **kwargs):
        kwargs['inNamespace'] = True
        Switch.__init__(self, name, **kwargs)
        Router.ID += 1
        self.switch_id = Router.ID

    @staticmethod
    def setup():
        return

    def start(self, controllers):
        pass

    def stop(self):
        self.deleteIntfs()

    def log(self, s, col="magenta"):
        print(T.colored(s, col))

class SimpleTopo(Topo):
    """
    Figure 2 topology:

          AS4
        /  |  \
      AS2--AS3--AS5
       |     \    |
      AS1     \   AS6

    Each AS has one router (R1..R6) and two hosts (hX-1, hX-2).
    Peer links (bidirectional) created in a fixed order to match zebra confs:
      R4-R2
      R4-R3
      R4-R5
      R2-R3
      R2-R1
      R3-R5
      R5-R6
      R3-R6
    """
    def __init__(self):
        super(SimpleTopo, self).__init__()

        def create_router_and_hosts(as_num: int):
            router = f'R{as_num}'
            self.addSwitch(router)
            for host_num in [1, 2]:
                host = self.addNode(f'h{as_num}-{host_num}')
                self.addLink(router, host)

        # Create AS1..AS6
        for asn in range(1, 7):
            create_router_and_hosts(asn)

        # Create inter-AS links in the exact order documented above
        self.addLink('R4', 'R2')  # -> R4-eth3 <-> R2-eth3
        self.addLink('R4', 'R3')  # -> R4-eth4 <-> R3-eth3
        self.addLink('R4', 'R5')  # -> R4-eth5 <-> R5-eth3
        self.addLink('R2', 'R3')  # -> R2-eth4 <-> R3-eth4
        self.addLink('R2', 'R1')  # -> R2-eth5 <-> R1-eth3
        self.addLink('R3', 'R5')  # -> R3-eth5 <-> R5-eth4
        self.addLink('R5', 'R6')  # -> R5-eth5 <-> R6-eth3
        self.addLink('R3', 'R6')  # -> R3-eth6 <-> R6-eth4

def parse_hostname(hostname):
    as_num, host_num = hostname.replace('h', '').split('-')
    return int(as_num), int(host_num)

def get_ip(hostname):
    as_num, host_num = parse_hostname(hostname)
    # Hosts in ASX live in (10+X).0.host/24, e.g., AS1 -> 11.0.x.1/24
    return f'{10+as_num}.0.{host_num}.1/24'

def get_gateway(hostname):
    as_num, host_num = parse_hostname(hostname)
    return f'{10+as_num}.0.{host_num}.254'

def start_webserver(net, hostname, text="Default web server"):
    host = net.getNodeByName(hostname)
    return host.popen(f"python webserver.py --text '{text}'", shell=True)

def main():
    os.system("rm -f /tmp/R*.log /tmp/R*.pid logs/*")
    os.system("mn -c >/dev/null 2>&1")
    os.system("pkill -9 bgpd > /dev/null 2>&1")
    os.system("pkill -9 zebra > /dev/null 2>&1")
    os.system('pkill -9 -f webserver.py')

    net = Mininet(topo=SimpleTopo(), switch=Router)
    net.start()
    for router in net.switches:
        router.cmd("sysctl -w net.ipv4.ip_forward=1")
        router.waitOutput()

    log(f"Waiting {args.sleep} seconds for sysctl changes to take effect...", 'yellow')
    sleep(args.sleep)

    for router in net.switches:
        if router.name == ROGUE_AS_NAME and not FLAGS_rogue_as:
            # Skip starting rogue by default; it will be started by start_rogue.sh / start_rogue_hard.sh
            continue
        router.cmd("ip link set dev lo up")
        router.waitOutput()
        router.cmd(f"/usr/lib/frr/zebra -f conf/zebra-{router.name}.conf -d -i /tmp/zebra-{router.name}.pid > logs/{router.name}-zebra-stdout 2>&1")
        router.waitOutput()
        router.cmd(f"/usr/lib/frr/bgpd -f conf/bgpd-{router.name}.conf -d -i /tmp/bgp-{router.name}.pid > logs/{router.name}-bgpd-stdout 2>&1", shell=True)
        router.waitOutput()
        log(f"Started zebra/bgpd on {router.name}")

    # Configure hosts
    for host in net.hosts:
        host.cmd(f"ifconfig {host.name}-eth0 {get_ip(host.name)}")
        host.cmd(f"route add default gw {get_gateway(host.name)}")

    # Start web servers:
    # - True origin service at AS1 (victim) -> 11.0.1.1
    # - Attacker service at AS6 -> to detect hijack easily
    log("Starting web servers", 'yellow')
    start_webserver(net, 'h1-1', "Default web server 2.1.1 (AS1)")
    start_webserver(net, 'h6-1', "*** Attacker web server 2.1.1 (AS6) ***")

    CLI(net, script=args.scriptfile)
    net.stop()
    os.system("pkill -9 bgpd")
    os.system("pkill -9 zebra")
    os.system('pkill -9 -f webserver.py')

if __name__ == "__main__":
    main()