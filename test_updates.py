import importlib
import json
import os
import Queue
import settings
import sys
import threading
import time


BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
DEVICES_PATH = "%s/Hosts/" % (BASE_PATH )
THIRTYBIRDS_PATH = "%s/thirtybirds_2_0" % (UPPER_PATH )

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)

from thirtybirds_2_0.Network.info import init as network_info_init
network_info = network_info_init()

def get_hostname():
    try:
        pos = args.index("-n") # pull hostname from command line argument, if there is one
        hostname = args[pos+1]
    except Exception as E:
        hostname = network_info.getHostName()
    return hostname

HOSTNAME = get_hostname()

from thirtybirds_2_0.Network.manager import init as network_init


def network_status_handler(msg):
    print "network_status_handler", msg
    print msg["hostname"]
    #if msg["hostname"] == "supercoolerA0":


def network_message_handler(msg):
    print "network_message_handler", msg

network = network_init(
    hostname=HOSTNAME,
    role="server",
    discovery_multicastGroup=settings.discovery_multicastGroup,
    discovery_multicastPort=settings.discovery_multicastPort,
    discovery_responsePort=settings.discovery_responsePort,
    pubsub_pubPort=settings.pubsub_pubPort,
    message_callback=network_message_handler,
    status_callback=network_status_handler
)


class Thirtybirds_Client_Monitor_Server(threading.Thread):
    def __init__(self, network, hostnames, update_period=45):
        threading.Thread.__init__(self)
        self.update_period = update_period
        self.current_clients = {}
        self.remembered_clients = {}
        self.network = network
        self.hostnames = hostnames
        self.queue = Queue.Queue()
        self.hosts = {}

    def empty_host_list(self):
        self.hosts = {}
        for hostname in self.hostnames:
            self.hosts[hostname] = {
                "present":False,
                "timestamp":False,
                "pickle_version":False,
                "git_pull_date":False
            }

    def add_to_queue(self, hostname, git_pull_date, pickle_version):
        self.queue.put((hostname, git_pull_date, pickle_version, time.time()))

    def print_current_clients(self):
        print ""
        print "CURRENT CLIENTS:"
        for hostname in self.hostnames:
            print "%s: %s : %s: %s: %s" % (hostname, self.hosts[hostname]["present"], self.hosts[hostname]["timestamp"], self.hosts[hostname]["pickle_version"], self.hosts[hostname]["git_pull_date"])

    def run(self):
        while True:
            self.empty_host_list()
            self.network.send("client_monitor_request", "")
            time.sleep(self.update_period)
            while not self.queue.empty():
                [hostname, git_pull_date, pickle_version, timestamp] = self.queue.get(True)
                #print ">>", hostname, git_pull_date, pickle_version, timestamp
                self.hosts[hostname]["present"] = True
                self.hosts[hostname]["timestamp"] = timestamp
                self.hosts[hostname]["pickle_version"] = pickle_version
                self.hosts[hostname]["git_pull_date"] = git_pull_date
            self.print_current_clients()


class Camera_Units():
    def __init__(self, network):
            self.network = network
    def capture_image(self, light_level_sequence_position):
        self.network.send("capture_image", light_level_sequence_position)
    def process_images_and_report(self):
        self.network.send("process_images_and_report", "")
    def send_update_command(self, cool=False, birds=False, update=False, upgrade=False):
        self.network.send("remote_update", [cool, birds, update, upgrade])
    def send_update_scripts_command(self):
        self.network.send("remote_update_scripts", "")
    def send_reboot(self):
        self.network.send("reboot")

camera_units = Camera_Units(network)
time.sleep(60)


hostnames = [
    "supercoolerA0","supercoolerA1","supercoolerA2","supercoolerA3","supercoolerA4","supercoolerA5","supercoolerA6","supercoolerA7","supercoolerA8","supercoolerA9","supercoolerA10","supercoolerA11",
    "supercoolerB0","supercoolerB1","supercoolerB2","supercoolerB3","supercoolerB4","supercoolerB5","supercoolerB6","supercoolerB7","supercoolerB8","supercoolerB9","supercoolerB10","supercoolerB11",
    "supercoolerC0","supercoolerC1","supercoolerC2","supercoolerC3","supercoolerC4","supercoolerC5","supercoolerC6","supercoolerC7","supercoolerC8","supercoolerC9","supercoolerC10","supercoolerC11",
    "supercoolerD0","supercoolerD1","supercoolerD2","supercoolerD3","supercoolerD4","supercoolerD5","supercoolerD6","supercoolerD7","supercoolerD8","supercoolerD9","supercoolerD10","supercoolerD11"
]
client_monitor_server = Thirtybirds_Client_Monitor_Server(network, hostnames)
client_monitor_server.daemon = True
client_monitor_server.start()



#camera_units.send_update_command(cool=True, birds=False, update=False, upgrade=False)
time.sleep(60)
camera_units.send_update_scripts_command()

#camera_units.send_update_command(cool=True, birds=False, update=False, upgrade=False)
#time.sleep(60)

#camera_units.send_update_command(cool=True, birds=False, update=False, upgrade=False)
#time.sleep(60)
#print "done"
#




