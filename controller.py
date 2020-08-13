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
# import networkx as nx
from ryu.lib.packet import icmp
from ryu.ofproto import ether
from ryu.topology import event, switches
from ryu.topology.api import get_all_switch, get_all_link
from ryu.app.wsgi import ControllerBase
import array
from ryu.app.ofctl.api import get_datapath

## {1:{2:w}}

def getTopology():
    pass

def find_min_distance(l, distances):
    if not l:
        return
    minNode = l[0]
    for n in l:
        if distances[n] < distances[minNode]:
            minNode = n 
    return minNode

def dijkstra(src, dest):
    graph = getTopology()

    if src not in graph:
        raise TypeError('The root of the shortest path tree cannot be found')
    if dest not in graph:
        raise TypeError('The target of the shortest path cannot be found')
    
    visited = [src]
    nodes = graph.keys()
    distances = {}
    predecessors = {}

    distances[src] = 0
    predecessors[src] = src 

    for node in nodes:
        if node in graph[src]:
            distances[node] = graph[src][node]
            predecessors[node] = src
        else:
            distances[node] = float('inf')
    
    while nodes != visited:
        nextNode = find_min_distance(list(set(nodes)-set(visited)), distances)
        visited.append(nextNode)
        for node in graph[nextNode]:
            if distances[nextNode] + graph[nextNode][node] < distances[node]:
                distances[node] = distances[nextNode] + graph[nextNode][node]
                predecessors[node] = nextNode

    path = []
    n = dest
    while n != src:
        path.append(n)
        n = predecessors[n]
    path.append(src)
    path.reverse()
    return path
    

def dpid_hostLookup(lmac):
    host_locate = {1: {'00:00:00:00:00:01'}, 2: {'00:00:00:00:00:02'}, 3: {'00:00:00:00:00:03', '00:00:00:00:00:04'},
                    4: {'00:00:00:00:00:05', '00:00:00:00:00:06', '00:00:00:00:00:07'}}
    for dpid, mac in host_locate.iteritems():
        if lmac in mac:
            return dpid

class dijkstra_switch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(dijkstra_switch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.dpid_to_port = {}
        # self.net = nx.DiGraph()
        # self.g = nx.DiGraph()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 2, match, actions)
    
    def add_flow(self, datapath, priority, match,inst=[]):
        ofp_parser = datapath.ofproto_parser
        mod = ofp_parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        
        if not self.dpid_to_port:
            links = get_all_link(self)

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        dst = eth.dst
        src = eth.src
        dpid = datapath.id        
        in_port = msg.match['in_port']
        self.mac_to_port.setdefault(dpid, {})

        self.mac_to_port[dpid][src] = in_port

        dst_dpid = dpid_hostLookup(dst)
        path = dijkstra(dpid, dst_dpid) 

        if len(path) == 1:
            if dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][dst]
            else:
                out_port = ofproto.OFPP_FLOOD
        else:
            next_dpid = path[1]
            out_port = self.getDpidPort(dpid, next_dpid)

        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            self.add_flow(datapath, in_port, dst, actions)

    def getDpidPort(self, src_dpid, dst_dpid):
        links = get_all_link(self)
        for link in links:
            if link.src.dpid == src_dpid and link.dst.dpid == dst_dpid:
                return link.src.port_no
        raise TypeError('link between %s and %s does not exist', src_dpid, dst_dpid)


        