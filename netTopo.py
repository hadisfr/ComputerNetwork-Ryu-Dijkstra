from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from subprocess import call

def myNetwork():

    net = Mininet( topo=None,
                   build=False,
                   ipBase='10.0.0.0/8', autoStaticArp=False)

    info( '*** Adding controller\n' )
    c0=net.addController(name='c0',
                      controller=RemoteController,
                         ip= '127.0.0.1',
                      port=6633)

    info( '*** Add switches\n')
    sw1 = net.addSwitch('sw1', cls=OVSKernelSwitch)
    sw2 = net.addSwitch('sw2', cls=OVSKernelSwitch)
    sw3 = net.addSwitch('sw3', cls=OVSKernelSwitch)

    info( '*** Add hosts\n')
    h1 = net.addHost('h1', cls=Host, ip='10.1.0.1',mac='00:00:00:00:00:01', defaultRoute=None)
    h2 = net.addHost('h2', cls=Host, ip='10.1.0.2',mac='00:00:00:00:00:02', defaultRoute=None)

    info( '*** Add links\n')
    net.addLink(h1, sw1)
    net.addLink(sw1, sw2)
    net.addLink(sw2, sw3)
    net.addLink(sw3,h2)

    info( '*** Starting network\n')
    net.build()

    for controller in net.controllers:
        controller.start()
    
    info( '*** Starting switches\n')
    net.get('sw1').start([c0])
    net.get('sw2').start([c0])
    net.get('sw3').start([c0])

    info( '*** Post configure switches and hosts\n')
    CLI(net)
    net.stop()


setLogLevel( 'info' )
topos = { 'mytopo': ( lambda: myNetwork() ) }


# if __name__ == '__main__':
#     myNetwork()
