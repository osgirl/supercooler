"""
TASKS:
    init:
        listen to API
        set up camera

    runtime:
        capture_image
        parse_capture
        classify_parsed_images
        send inventory and captured image to conductor
        send status data with attar

API for Server:
    capture_image
    parse_capture
    classify_parsed_images  ( sends images to Server when finished )
    capture_parse_classify  ( macro process for all three )
    send_status [ initialized | capture_image | parse_capture | classify_parsed_images | finished ]
    send_captures
    send_parsed_images
    send_inventory
    send_log ( loglevel )

ATTAR:
    writes to terminal, log file, and publishes to ZMQ
    data types:
        debug:
        trace:
        exceptions:
        events: ( loaded, lost_connection, starting capture, finished can parse (10 found), etc )

"""

import importlib
import json
import os
import settings 
import sys
import threading
import time
import subprocess
import base64
import Queue

from thirtybirds_2_0.Network.manager import init as network_init
from thirtybirds_2_0.Network.email_simple import init as email_init
from thirtybirds_2_0.Adaptors.Cameras.elp import init as camera_init
from thirtybirds_2_0.Updates.manager import init as updates_init

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
DEVICES_PATH = "%s/Hosts/" % (BASE_PATH )
THIRTYBIRDS_PATH = "%s/thirtybirds" % (UPPER_PATH )

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)


class Main(threading.Thread):
    def __init__(self, hostname, network):
        threading.Thread.__init__(self)
        self.hostname = hostname
        self.network = network
        self.camera = camera_init("/home/pi/supercooler/Captures/")
        self.queue = Queue.Queue()

    def add_to_queue(self, topic, msg):
        self.queue.put((topic, msg))

    def capture_image_and_save(self, filename):
        self.camera.take_capture(filename)


    def run(self):
        while True:
            topic, msg = self.queue.get(True)
            if topic == "capture_image":
                filename = "{}_{}.png".format(self.hostname[:11], cap) 
                self.capture_image_and_save(filename)


        ###  ###


def process_img(img):
    return hostname

def network_status_handler(msg):
    print "network_status_handler", msg

def network_message_handler(msg):
    print "network_message_handler", msg
    topic = msg[0]
    data = msg[1]
    #host, sensor, data = yaml.safe_load(msg[1])
    if topic == "__heartbeat__":
        print "heartbeat received", msg

    if topic == "capture_image":
        main.add_to_queue(topic, data)
        

    elif topic == "reboot":
        print "reboot!"
        os.system("sudo reboot now")

    elif topic == "get_beer": 
        #img = capture_img()
        #data = process_img(img)
        filename = "capture" + hostname[11:] + ".png"
        main.camera.take_capture(filename)
        time.sleep(5)
        main.email.send("ac-smart-cooler@googlegroups.com", "camera capture from %s" % (main.hostname),"test", "/home/pi/supercooler/Captures/" + filename)

        network.send("found_beer", "")

    elif topic == hostname:
        print "testing png file sending"

        filename = "capture" + hostname[11:] + ".png"
        main.camera.take_capture(filename)

        time.sleep(5)

        with open("/home/pi/supercooler/Captures/" + filename, "rb") as f:
            data = f.read()
            network.send("found_beer", base64.b64encode(data))

    elif topic == "remote_update":
        # this is my hacky way to update the repos, make this better later
        print "remote update go!"

        [cool, birds, update, upgrade] = eval(msg[1])
        if cool:
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/supercooler')

        if birds:
            subprocess.call(['sudo', 'git', 'pull'], cwd='home/pi/thirtybirds_2_0')

        print "it's done!"
        network.send("update_complete", hostname)

    elif topic == "remote_update_scripts":
        print "run update scripts"
        updates_init("/home/pi/supercooler", False, True)

        print "it's done!"
        network.send("update_complete", hostname)

main = None


def init(HOSTNAME):
    global network
    network = network_init(
        hostname=HOSTNAME,
        role="client",
        discovery_multicastGroup=settings.discovery_multicastGroup,
        discovery_multicastPort=settings.discovery_multicastPort,
        discovery_responsePort=settings.discovery_responsePort,
        pubsub_pubPort=settings.pubsub_pubPort,
        message_callback=network_message_handler,
        status_callback=network_status_handler
    )

    #global hostname
    #hostname = HOSTNAME
    global main 
    main = Main(HOSTNAME,  network)
    main.daemon = True
    main.start()

    network.subscribe_to_topic("system")  # subscribe to all system messages
    network.subscribe_to_topic("reboot")
    network.subscribe_to_topic("process_images_and_report")
    network.subscribe_to_topic("get_beer")
    network.subscribe_to_topic("remote_update")
    network.subscribe_to_topic(HOSTNAME)
    
    