import importlib
import json
import os
import settings
import sys
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
time.sleep(120)

camera_units.send_update_command(cool=True, birds=True, update=True, upgrade=True)
time.sleep(60)

camera_units.send_update_scripts_command()




