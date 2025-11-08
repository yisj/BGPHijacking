#!/usr/bin/env python
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.cli import CLI
from time import sleep
from argparse import ArgumentParser
import os, termcolor as T

setLogLevel('info')
parser = ArgumentParser("BGP Hijacking Fig.2 Topology")
parser.add_argument('--rogue', action="store_true", default=False)
parser.add_argument('--scriptfile', default=None)
parser.add_argument('--sleep', default=3, type=int)
args = parser.parse_args()

FLAGS_rogue_as = args.rogue
ROGUE_AS_NAME = 'R6'   # attacker

def log(s, col="green"): print(T.colored(s, col))

class Router(Topo):
    pass

class Fig2Topo(Topo):
    def __init__(self):
        super(Fig2Topo,self).__init__()
        def add_as(n):
            r = f'R{n}'
            self.addSwitch(r)
            for h in (1,2):
                hn = f'h{n}-{h}'
                self.addHost(hn)
                self.addLink(r, hn)
        for n in (1,2,3,4,5,6): add_as(n)

        # ---- Inter-AS links (order matters for eth index mapping) ----
        # L12
        self.addLink('R1','R2')
        # L23
        self.addLink('R2','R3')
        # L35
        self.addLink('R3','R5')
        # L25
        self.addLink('R2','R5')
        # L24
        self.addLink('R2','R4')
        # L34
        self.addLink('R3','R4')
        # L45
        self.addLink('R4','R5')
        # L36
        self.addLink('R3','R6')
        # L56
        self.addLink('R5','R6')

def parse_hostname(hostname):
    as_num, host_num = hostname.replace('h','').split('-')
    return int(as_num), int(host_num)

def get_ip(hostname):
    asn, hostn = parse_hostname(hostname)
    return f'{10+asn}.0.{hostn}.1/24'

def get_gateway(hostname):
    asn, hostn = parse_hostname(hostname)
    return f'{10+asn}.0.{hostn}.254'

def start_webserver(net, hostname, text):
    host = net.getNodeByName(hostname)
    return host.popen(f"python webserver.py --text '{text}'", shell=True)

def main():
    os.system("rm -f /tmp/R*.log /tmp/R*.pid logs/*")
    os.system("mn -c >/dev/null 2>&1")
    os.system("pkill -9 bgpd >/dev/null 2>&1")
    os.system("pkill -9 zebra >/dev/null 2>&1")
    os.system("pkill -9 -f webserver.py >/dev/null 2>&1")

    net = Mininet(topo=Fig2Topo())
    net.start()

    # enable IP forwarding and start FRR daemons per router
    for sw in net.switches:
        sw.cmd("sysctl -w net.ipv4.ip_forward=1")
    log(f"Waiting {args.sleep}s for sysctl...", "yellow"); sleep(args.sleep)

    for r in net.switches:
        if r.name == ROGUE_AS_NAME and not FLAGS_rogue_as:
            continue
        r.cmd("ip link set dev lo up")
        r.cmd(f"/usr/lib/frr/zebra -f conf/zebra-{r.name}.conf -d -i /tmp/zebra-{r.name}.pid > logs/{r.name}-zebra-stdout 2>&1")
        r.cmd(f"/usr/lib/frr/bgpd  -f conf/bgpd-{r.name}.conf  -d -i /tmp/bgpd-{r.name}.pid  > logs/{r.name}-bgpd-stdout 2>&1")
        log(f"Started FRR on {r.name}")

    # hosts IP & default gw
    for h in net.hosts:
        h.cmd(f"ifconfig {h.name}-eth0 {get_ip(h.name)}")
        h.cmd(f"route add default gw {get_gateway(h.name)}")

    # Web servers: True origin (AS1) vs Attacker (AS6)
    log("Starting web servers", "yellow")
    start_webserver(net, 'h1-1', "Default web server (AS1)")
    start_webserver(net, 'h6-1', "*** Attacker web server (AS6) ***")

    CLI(net, script=args.scriptfile)
    net.stop()
    os.system("pkill -9 bgpd"); os.system("pkill -9 zebra")
    os.system("pkill -9 -f webserver.py")

if __name__ == '__main__':
    main()