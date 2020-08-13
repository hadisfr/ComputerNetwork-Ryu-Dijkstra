                                                                                             
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from subprocess import call
import random


logging.getLogger().setLevel(logging.INFO)
hostList = 7 * [0]

class MyTopo(Topo):

    def __init__(self, ipBase='10.0.0.0/8'):
        Topo.__init__(self)

        
        info( '*** Add switches\n')
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')


        info( '*** Add hosts\n')
        global hostList
        for i in range(1, 8):
            hostList[i-1] = self.addHost('h%s'%i, cls=Host, ip='10.0.0.%s'%i,mac='00:00:00:00:00:0%s'%i, defaultRoute=None)

        info( '*** Add links\n')
        self.addLink(hosts[0], s1, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(hosts[1], s2, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(hosts[2], s3, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(hosts[3], s3, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(hosts[4], s4, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(hosts[5], s4, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(hosts[6], s4, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(s2,s1, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(s3,s1, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(s2,s3, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(s3,s4, cls = TCLink, bw = random.uniform(1,5))
        self.addLink(s4,s2, cls = TCLink, bw = random.uniform(1,5))





def attack():
    h1 = net.get('h1')
    h1.cmd('hping3 -c 3 h2')


info( '*** Starting network\n')

topo = MyTopo()
net = Mininet(topo, controller=lambda name: RemoteController(name,
              ip= '127.0.0.1', protocol= 'tcp', port= 6633), autoSetMacs= True)
net.start()
attack()
CLI(net)
net.stop()




# def NetworkTopo(Topo):

#     net = Mininet( topo=None,
#                    build=False,
#                    ipBase='10.0.0.0/8', autoStaticArp=False)

#     info( '*** Adding controller\n' )
#     c0=net.addController( name='c0', controller=RemoteController,
#                     ip= '127.0.0.1', port=6633)


#     info( '*** Add switches\n')
#     s1 = self.addSwitch('s1')
#     s2 = self.addSwitch('s2')
#     s3 = self.addSwitch('s3')
#     s4 = self.addSwitch('s4')

#     info( '*** Add hosts\n')
#     hosts = [0] * 7
#     hosts[0] = self.addHost('h1', cls=Host, ip='10.0.0.1',mac='00:00:00:00:00:01', defaultRoute=None)
#     hosts[1] = self.addHost('h2', cls=Host, ip='10.0.0.2',mac='00:00:00:00:00:02', defaultRoute=None)
#     hosts[2] = self.addHost('h3', cls=Host, ip='10.0.0.3',mac='00:00:00:00:00:03', defaultRoute=None)
#     hosts[3] = self.addHost('h4', cls=Host, ip='10.0.0.4',mac='00:00:00:00:00:04', defaultRoute=None)
#     hosts[4] = self.addHost('h5', cls=Host, ip='10.0.0.5',mac='00:00:00:00:00:05', defaultRoute=None)
#     hosts[5] = self.addHost('h6', cls=Host, ip='10.0.0.6',mac='00:00:00:00:00:06', defaultRoute=None)
#     hosts[6] = self.addHost('h7', cls=Host, ip='10.0.0.7',mac='00:00:00:00:00:07', defaultRoute=None)


#     info( '*** Add links\n')
#     self.addLink(hosts[0], s1, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(hosts[1], s2, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(hosts[2], s3, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(hosts[3], s3, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(hosts[4], s4, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(hosts[5], s4, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(hosts[6], s4, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(s2,s1, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(s3,s1, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(s2,s3, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(s3,s4, cls = TCLink, bw = random.uniform(1,5))
#     self.addLink(s4,s2, cls = TCLink, bw = random.uniform(1,5))

#     info( '*** Starting network\n')
#     net.build()

#     for controller in net.controllers:
#         controller.start()
    
#     info( '*** Starting switches\n')
#     net.get('s1').start([c0])
#     net.get('s2').start([c0])
#     net.get('s3').start([c0])
#     net.get('s4').start([c0])

#     info( '*** Post configure switches and hosts\n')
#     CLI(net)
#     net.stop()



# setLogLevel( 'info' )
# topos = { 'mytopo': ( lambda: NetworkTopo() ) }


# def simpleTest():
#     "Create and test a simple network"
#     topo = SingleSwitchTopo(n=4)
#     net = Mininet(topo)
#     net.start()
#     print "Dumping host connections"
#     dumpNodeConnections(net.hosts)
#     print "Testing network connectivity"
#     net.pingAll()
#     net.stop()

# if __name__ == '__main__':
#     # Tell mininet to print useful information
#     setLogLevel('info')
#     simpleTest()