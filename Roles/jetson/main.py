import base64
import json
import os
import Queue
import subprocess
import datetime
import time
import threading
import settings

from thirtybirds_2_0.Network.manager import init as network_init

class Thirtybirds_Client_Monitor_Server(threading.Thread):
    def __init__(self, network, hostnames, update_period=60):
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
            print "%s: %s : %s: %s: %s" % (hostname, self.hosts[hostname]["present"],
                self.hosts[hostname]["timestamp"], self.hosts[hostname]["pickle_version"],
                self.hosts[hostname]["git_pull_date"])

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


class Main(): # rules them all
    def __init__(self, network):
        self.network = network
        self.gdir_captures = "0BzpNPyJoi6uoSGlhTnN5RWhXRFU"

        self.light_level_sequence = [10, 5, 0]
        self.camera_units = Camera_Units(self.network)
        self.camera_capture_delay = 25
        self.last_closure = 0

        hostnames = [
            "supercoolerA0","supercoolerA1","supercoolerA2","supercoolerA3","supercoolerA4",
            "supercoolerA5","supercoolerA6","supercoolerA7","supercoolerA8","supercoolerA9",
            "supercoolerA10","supercoolerA11",
            "supercoolerB0","supercoolerB1","supercoolerB2","supercoolerB3","supercoolerB4",
            "supercoolerB5","supercoolerB6","supercoolerB7","supercoolerB8","supercoolerB9",
            "supercoolerB10","supercoolerB11",
            "supercoolerC0","supercoolerC1","supercoolerC2","supercoolerC3","supercoolerC4",
            "supercoolerC5","supercoolerC6","supercoolerC7","supercoolerC8","supercoolerC9",
            "supercoolerC10","supercoolerC11",
            "supercoolerD0","supercoolerD1","supercoolerD2","supercoolerD3","supercoolerD4",
            "supercoolerD5","supercoolerD6","supercoolerD7","supercoolerD8","supercoolerD9",
            "supercoolerD10","supercoolerD11",
            "supercooler-hardware"
        ]

        self.client_monitor_server = Thirtybirds_Client_Monitor_Server(network, hostnames)
        self.client_monitor_server.daemon = True
        self.client_monitor_server.start()

    def client_monitor_add_to_queue(self,hostname, git_pull_date, pickle_version):
        self.client_monitor_server.add_to_queue(hostname, git_pull_date, pickle_version)

    def get_training_images(self):
        if time.time() - self.last_closure < 360:
            print "no action taken, waiting for parse/upload to finish..."
            return

        self.last_closure = time.time()

        # create directories on google drive for storing captures
        timestamp = time.strftime("%Y-%m-%d-%H-%m-%S")
        dir_captures_now = mkdir_gdrive(self.gdir_captures, 'captures_' + timestamp)
        dir_unprocessed = mkdir_gdrive(dir_captures_now, 'unprocessed')
        dir_annotated = mkdir_gdrive(dir_captures_now, 'annotated')
        dir_parsed = mkdir_gdrive(dir_captures_now, 'parsed')
        
        # tell camera units to captures images at each light level
        for light_level in range(3):
            network.send("set_light_level", self.light_level_sequence[light_level])
            time.sleep(1)
            network.send("capture_and_upload",
                str([timestamp, light_level, dir_unprocessed, light_level == 0]))

            time.sleep(self.camera_capture_delay)

        # turn off the lights
        network.send("set_light_level", 0)

        # tell camera units to parse images and send back the data
        network.send("parse_and_annotate", str([timestamp, dir_annotated, dir_parsed]))

        print "current UTC time is", datetime.datetime.utcnow()
        print "parse/upload in process, check google drive in five minutes."

main = None

def mkdir_gdrive(parent_dir, new_dir):
    if parent_dir == None:
        mkdir_stdout = \
            subprocess.check_output(['gdrive', 'mkdir', new_dir])
    else:
        mkdir_stdout = \
            subprocess.check_output(['gdrive', 'mkdir', '-p', parent_dir, new_dir])

    return mkdir_stdout.split(" ")[1]


def network_status_handler(msg):
    print "network_status_handler", msg

def network_message_handler(msg):
    try:
        global main
        print "network_message_handler", msg
        topic = msg[0]

        if len(msg[1]) > 0:
            payload = eval(msg[1])
        else:
            payload = None

        if topic == "__heartbeat__":
            print "heartbeat received", msg

        if topic == "receive_image_overlay":
            pass
            # images.receive_and_save(payload[0],payload[1])

        if topic == "update_complete":
            print 'update complete for host: ', msg[1]

        if topic == "client_monitor_response":
            if payload == None:
                return
            if main:
                main.client_monitor_add_to_queue(payload[0],payload[2],payload[1])

        if topic == "door_closed":
            print "door closed"
            main.get_training_images()
            #main.door_close_event_handler()

        if topic == "door_opened":
            print "door opened"

    except Exception as e:
        print "exception in network_message_handler", e


def init(HOSTNAME):
    global main
    global network

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
    network.subscribe_to_topic("system")  # subscribe to all system messages
    network.subscribe_to_topic("update_complete")
    network.subscribe_to_topic("client_monitor_response")

    network.subscribe_to_topic("door_closed")
    network.subscribe_to_topic("door_opened")

    main = Main(network)
    return main
