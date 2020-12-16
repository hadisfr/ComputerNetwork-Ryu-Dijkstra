from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, arp, ipv4
from ryu.lib.packet import ether_types
from ryu.lib import mac
from ryu.lib.mac import haddr_to_bin
from ryu.controller import mac_to_port
from ryu.ofproto import inet
from ryu.lib.packet import icmp
from ryu.ofproto import ether
from ryu.topology import event, switches
from ryu.topology.switches import LLDPPacket
from ryu.topology.api import get_switch, get_link
from ryu.app.wsgi import ControllerBase
import array
from ryu.app.ofctl.api import get_datapath
import json
import copy
from datetime import datetime


def inv(x):
    return list(filter(lambda a: not a.startswith("_"), dir(x)))


class dijkstra_switch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(dijkstra_switch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.dpid_to_port = {}
        self.topo_raw_switches = []
        self.topo_raw_links = []
        self.dijkstra_predecessors = {}
        self.topology, self.host_locate = self.read_topology("topology.json")
        self.mac_to_inteface_name = {"00:00:00:00:00:0%d" % (host + 1): "h%d" % (host + 1) for host in range(7)}
        self.gen_dijkstra_trees()
        self.flow_rate_file = open("flowRate.tr", "w")
        self.packet_trace = open("packetTrace.tr", "w")

    def __del__(self):
        self.flow_rate_file.close()
        self.packet_trace.close()

    def log(self, msg, file):
        file.write(str(datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]) + "\t" + msg + "\n")

    def read_topology(self, addr):
        with open(addr) as f:
            data = json.load(f)
            links = data["weights"]
            hosts = data["hosts"]

        topo = {}
        for link in links:
            src, dst, weight = link
            topo.setdefault(src, {})
            topo.setdefault(dst, {})
            topo[src][dst] = weight
            topo[dst][src] = weight

        return topo, hosts

    def gen_dijkstra_trees(self):
        self.dijkstra_predecessors = {node: self.dijkstra(node) for node in self.topology}

    def dijkstra(self, src):
        def initiate(src):
            visited = {src}
            nodes = set(self.topology.keys())
            distances = {src: 0}
            predecessors = {src: src}
            for node in nodes:
                if node in self.topology[src]:
                    distances[node] = self.topology[src][node]
                    predecessors[node] = src
                else:
                    distances[node] = float("inf")
            return nodes, visited, distances, predecessors

        def update_distances(distances, predecessors):
            for node in self.topology.get(nextNode, []):
                if distances[nextNode] + self.topology[nextNode][node] < distances[node]:
                    distances[node] = distances[nextNode] + self.topology[nextNode][node]
                    predecessors[node] = nextNode

        def find_min_distance(candidate_nodes, distances):
            if not candidate_nodes:
                raise ValueError("empty candidate nodes")
            candidate_nodes = list(candidate_nodes)
            minNode = candidate_nodes[0]
            for n in candidate_nodes:
                if distances[n] < distances[minNode]:
                    minNode = n
            return minNode

        nodes, visited, distances, predecessors = initiate(src)

        while nodes != visited:
            nextNode = find_min_distance(nodes - visited, distances)
            visited.add(nextNode)
            update_distances(distances, predecessors)

        return predecessors

    def get_path(self, src, dst):
        if src not in self.dijkstra_predecessors:
            raise LookupError("The source node %s cannot be found" % src)
        if dst not in self.dijkstra_predecessors:
            raise LookupError("The destination node %s cannot be found" % dst)

        path = []
        node = dst
        while node != src:
            path.append(node)
            node = self.dijkstra_predecessors[src][node]
        path.append(src)
        return list(reversed(path))

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)
        self.log(str(datapath.id), self.flow_rate_file)

    def get_core_port(self, src_dpid, dst_dpid):
        for link in self.topo_raw_links:
            if (link.src.dpid == src_dpid and link.dst.dpid == dst_dpid):
                return link.src.port_no
        raise RuntimeError("link between %s and %s does not exist" % (src_dpid, dst_dpid))

    def get_edge_port(self, src_dpid, dst_mac):
        if dst_mac in self.mac_to_port[src_dpid]:
            return self.mac_to_port[src_dpid][dst_mac]
        else:
            raise RuntimeError("link between %s and %s does not exist" % (src_dpid, dst_mac))

    def is_lldp(self, msg):
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg.data)
            return True
        except LLDPPacket.LLDPUnknownFormat:
            return False

    def is_multicast(self, mac_addr):
        return mac_addr == "ff:ff:ff:ff:ff:ff"

    def is_tcp(self, pkt):
        res = False
        for protocol in pkt.protocols:
            if hasattr(protocol, "protocol_name") and protocol.protocol_name == "tcp":
                res = True
        return res

    def route_unicast(self, src_mac, dst_mac, src_dpid, dst_dpid, datapath, in_port, pkt, ofproto, parser):
        path = self.get_path(src_dpid, dst_dpid)
        if len(path) == 0:
            raise RuntimeError("Invalid path")
        self.logger.info("%s -> %s : %s -> %s via %s" %
                         (self.mac_to_inteface_name[src_mac], self.mac_to_inteface_name[dst_mac],
                          src_dpid, dst_dpid, path))

        if len(path) == 1:  # directly forward to host
            out_port = self.get_edge_port(src_dpid, dst_mac)
        else:  # forward to next hop
            out_port = self.get_core_port(src_dpid, path[1])

        if self.is_tcp(pkt):
            pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
            self.logger.info("in_port: %s,\tout_port: %s,\tpath: %s", in_port, out_port, str(path))
            self.log("%s %s %s %s" % (pkt_ipv4.identification, src_mac, dst_mac, str(path).replace(" ", "")),
                     self.packet_trace)

        return out_port

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg

        # Ignore LLDPPackets used for topology discovery
        if self.is_lldp(msg):
            return

        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        src_mac = eth.src
        dst_mac = eth.dst

        in_port = msg.match["in_port"]

        src_dpid = datapath.id
        self.mac_to_port.setdefault(src_dpid, {})
        self.mac_to_port[src_dpid][src_mac] = in_port
        dst_dpid = self.host_locate.get(dst_mac)

        if dst_mac not in self.mac_to_inteface_name and not self.is_multicast(dst_mac):
            return

        if self.is_multicast(dst_mac):
            out_port = ofproto.OFPP_FLOOD
        else:
            out_port = self.route_unicast(src_mac, dst_mac, src_dpid, dst_dpid, datapath, in_port, pkt, ofproto, parser)

        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 2, match, actions)

    @set_ev_cls(event.EventSwitchEnter)
    def handler_switch_enter(self, ev):
        sw = ev.switch
        self.logger.info("switch %s entered" % sw.dp.id)

        for port in sw.ports:
            self.mac_to_inteface_name[port.hw_addr] = port.name.decode()
        # The Function get_switch(self, None) outputs the list of switches.
        self.topo_raw_switches = copy.copy(get_switch(self, None))
        # The Function get_link(self, None) outputs the list of links.
        self.topo_raw_links = copy.copy(get_link(self, None))
