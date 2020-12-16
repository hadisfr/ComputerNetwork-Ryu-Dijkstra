#!/usr/bin/env python3

import json
import random
import threading
import time

from datetime import datetime
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.node import Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


class Topology(Topo):
    def __init__(self):
        Topo.__init__(self)

        hosts_cfg, switches_cfg, links_cfg = self.read_topology("topology.json")
        hosts = {}
        switches = {}

        info("*** Add switches\n")
        for sw_cfg in switches_cfg:
            switches[sw_cfg] = self.addSwitch(str(sw_cfg))

        info("*** Add hosts\n")
        for host_mac in hosts_cfg.keys():
            hosts[host_mac] = self.addHost("h%s" % host_mac[-1], ip="10.0.0.%s" % host_mac[-1], mac=host_mac,
                                           cls=Host, defaultRoute=None)

        info("*** Add links\n")
        for src, dst, weight in links_cfg:
            self.addLink(switches[src], switches[dst], cls=TCLink, bw=weight)
        for host_mac, sw in hosts_cfg.items():
            self.addLink(hosts[host_mac], switches[sw], cls=TCLink, bw=1)

    def read_topology(self, addr):
        with open(addr) as f:
            data = json.load(f)
            links = data["weights"]
            hosts = data["hosts"]
            switches = set()
        for src, dst, weight in links:
            switches.add(src)
            switches.add(dst)

        return hosts, switches, links


def change_bandwith(link):
    weight = random.uniform(1, 5)
    intfs = [link.intf1, link.intf2]
    info("link %s - %s:\t" % tuple(intfs))
    intfs[0].config(bw=weight)
    intfs[1].config(bw=weight)
    info("\n")


def manage_links(net):
    nodes = net.switches + net.hosts
    links = set()
    for node in nodes:
        for intf in node.intfList():
            if intf.link:
                links.add(intf.link)
    for link in links:
        change_bandwith(link)


def run_cmd(h, cmdStr):
    h.cmd(cmdStr)


def send_tcp_packets(net):
    threads = []
    for host in net.hosts:
        targetHost = random.choice(list(set(net.hosts) - {host}))
        target_ip = targetHost.IP()
        cmdStr = "hping3 -c 1 -d 100000 %s &" % target_ip
        thread = threading.Thread(target=run_cmd, args=[host, cmdStr])
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()


def run(net):
    time_counter = 0
    unit = 0.1
    info("start of execution\n")
    info("%s\n" % datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
    while time_counter * unit < 6:
        time.sleep(unit)
        send_tcp_packets(net)
        time_counter += 1
        if time_counter * unit % 10 == 0:
            manage_links(net)
    info("%s\n" % datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
    info("end of execution\n")


def main():
    setLogLevel("info")

    info("*** Starting network\n")

    for i in range(5):
        info("round %d\n" % (i + 1))
        topo = Topology()
        net = Mininet(topo, controller=lambda name: RemoteController(name,
                      ip="127.0.0.1", protocol="tcp", port=6633), autoSetMacs=True)
        net.start()
        time.sleep(7)
        run(net)
        # CLI(net)
        net.stop()
        time.sleep(15)


if __name__ == '__main__':
    main()
