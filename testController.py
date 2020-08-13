from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology.api import get_all_switch, get_all_link
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
import json
import copy


class ExampleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ExampleSwitch13, self).__init__(*args, **kwargs)
        # initialize mac address table.
        self.mac_to_port = {}
        self.dpid_to_port = {}
        self.topology_api_app = self        

    @set_ev_cls(event.EventSwitchEnter)
    def get_topology_data(self, ev):
        switch_list = get_switch(self.topology_api_app, None)
        switches=[switch.dp.id for switch in switch_list]
        links_list = get_link(self.topology_api_app, None)
        links=[(link.src.dpid,link.dst.dpid,{'port':link.src.port_no}) for link in links_list]
        print(links)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install the table-miss flow entry.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 2, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # construct flow_mod message and send it.
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        shouldLog = False

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        # get Datapath ID to identify OpenFlow switches.

        # link_list = copy.copy(get_all_link(self))
        # link_list_body = json.dumps([ link.to_dict() for link in link_list ])
        # print("links:")
        # for link in link_list:
        #     print(link)

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})


        # analyse the received packets using the packet library.
        pkt = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)
        dst = eth_pkt.dst
        src = eth_pkt.src

        # get the received port number from packet_in message.
        in_port = msg.match['in_port']
        

        for p in pkt.protocols:
            if hasattr(p,'protocol_name') and p.protocol_name == 'tcp':
                shouldLog = True

        # if shouldLog and not self.dpid_to_port:
        #     links = get_all_link(self)
        #     print(dpid)
        #     for link in links:
        #         l = link.to_dict()
        #         print(l)
        #     self.dpid_to_port = {'a':1}

        if shouldLog:
            self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)
            for p in pkt.protocols:
                print(p.protocol_name)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        # if the destination mac address is already learned,
        # decide which port to output the packet, otherwise FLOOD.
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        # construct action list.
        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time.
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions)

        # construct packet_out message and send it.
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions,
                                  data=msg.data)
        datapath.send_msg(out)




class TopoStructure():
    def __init__(self, *args, **kwargs):
        self.topo_raw_switches = []
        self.topo_raw_links = []
        self.topo_links = []


    def print_links(self, func_str=None):
        # Convert the raw link to list so that it is printed easily
        print("Current Links:")
        for l in self.topo_raw_links:
            print (l)

    def print_switches(self, func_str=None):
        print(" \t"+str(func_str)+": Current Switches:")
        for s in self.topo_raw_switches:
            print (" \t\t"+str(s))

    def switches_count(self):
        return len(self.topo_raw_switches)

    def convert_raw_links_to_list(self):
        # Build a  list with all the links [((srcNode,port), (dstNode, port))].
        # The list is easier for printing.
        self.lock.acquire()
        self.topo_links = [((link.src.dpid, link.src.port_no),
                            (link.dst.dpid, link.dst.port_no))
                           for link in self.topo_raw_links]
        self.lock.release()

    def convert_raw_switch_to_list(self):
        # Build a list with all the switches ([switches])
        self.lock.acquire()
        self.topo_switches = [(switch.dp.id, 1) for switch in self.topo_raw_switches]
        self.lock.release()

    """
    Adds the link to list of raw links
    """
    def bring_up_link(self, link):
        self.topo_raw_links.append(link)

    """
    Check if a link with specific nodes exists.
    """
    def check_link(self,sdpid, sport, ddpid, dport):
        for i, link in self.topo_raw_links:
            if ((sdpid, sport), (ddpid, dport)) == ((link.src.dpid, link.src.port_no), (link.dst.dpid, link.dst.port_no)):
                return True
        return False

    """
    Finds the shortest path from source s to destination d.
    Both s and d are switches.
    """
    def find_shortest_path(self, s):
        s_count = self.switches_count()
        s_temp = s
        visited = []
        shortest_path = {}

        while s_count != len(visited):
            print(visited)
            visited.append(s_temp)
            print (visited)
            print ("s_temp 1: " + str(s_temp))
            for l in self.find_links_with_src(s_temp):
                print ("\t"+str(l))
                if l.dst.dpid not in visited:
                    print ("\t\tDPID dst: "+ str(l.dst.dpid))
                    if l.src.dpid in shortest_path:
                        shortest_path[l.dst.dpid] += 1
                        print("\t\t\tdpid found. Count: "+str(shortest_path[l.dst.dpid]))
                    else:
                        print("\t\t\tdpid not found.")
                        shortest_path[l.dst.dpid] = 0
            print ("shortest_path: "+str(shortest_path))
            min_val = min(shortest_path.itervalues())
            t = [k for k,v in shortest_path.iteritems() if v == min_val]
            s_temp = t[0]
            print  ("s_temp 2: " + str(s_temp)+"\n")
        return shortest_path

    """
    Finds the dpids of destinations where the links' source is s_dpid
    """
    def find_dst_with_src(self, s_dpid):
        d = []
        for l in self.topo_raw_links:
            if l.src.dpid == s_dpid:
                d.append(l.dst.dpid)
        return d

    """
    Finds the list of link objects where links' src dpid is s_dpid
    """
    def find_links_with_src(self, s_dpid):
        d_links = []
        for l in self.topo_raw_links:
            if l.src.dpid == s_dpid:
                d_links.append(l)
        return d_links

    """
    Returns a link object that has in_dpid and in_port as either source or destination dpid and port.
    """
    def link_with_src_dst_port(self, in_port, in_dpid):
        for l in self.topo_raw_links:
            if (l.src.dpid == in_dpid and l.src.port_no == in_port) or (l.dst.dpid == in_dpid and l.src.port_no == in_port):
                return l
        return None
    """
    Returns a link object that has in_dpid and in_port as either source dpid and port.
    """
    def link_with_src_port(self, in_port, in_dpid):
        for l in self.topo_raw_links:
            if (l.src.dpid == in_dpid and l.src.port_no == in_port) or (l.dst.dpid == in_dpid and l.src.port_no == in_port):
                return l
        return None