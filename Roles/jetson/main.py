import base64
import json
import os
import Queue
import subprocess
import time
import threading
import settings
import yaml
import cv2

from thirtybirds_2_0.Network.manager import init as network_init

from web_interface import WebInterface
from classifier import Classifier

class Main(): # rules them all
    def __init__(self, network):
        self.network = network
        self.capture_path = "/home/pi/supercooler/Captures/"
        self.parsed_capture_path = "/home/pi/supercooler/ParsedCaptures/"

        hostnames = [
            "supercoolerA0","supercoolerA1","supercoolerA2","supercoolerA3","supercoolerA4","supercoolerA5","supercoolerA6","supercoolerA7","supercoolerA8","supercoolerA9","supercoolerA10","supercoolerA11",
            "supercoolerB0","supercoolerB1","supercoolerB2","supercoolerB3","supercoolerB4","supercoolerB5","supercoolerB6","supercoolerB7","supercoolerB8","supercoolerB9","supercoolerB10","supercoolerB11",
            "supercoolerC0","supercoolerC1","supercoolerC2","supercoolerC3","supercoolerC4","supercoolerC5","supercoolerC6","supercoolerC7","supercoolerC8","supercoolerC9","supercoolerC10","supercoolerC11",
            "supercoolerD0","supercoolerD1","supercoolerD2","supercoolerD3","supercoolerD4","supercoolerD5","supercoolerD6","supercoolerD7","supercoolerD8","supercoolerD9","supercoolerD10","supercoolerD11"
        ]

        self.client_monitor_server = Thirtybirds_Client_Monitor_Server(network, hostnames)
        self.client_monitor_server.daemon = True
        self.client_monitor_server.start()

    def client_monitor_add_to_queue(self,hostname, git_pull_date, pickle_version):
        self.client_monitor_server.add_to_queue(hostname, git_pull_date, pickle_version)

main = None

def network_status_handler(msg):
    print "network_status_handler", msg

def network_message_handler(msg):
    try:
        global main
        #print "network_message_handler", msg
        topic = msg[0]
        payload = eval(msg[1])
        #print "topic", topic
        if topic == "__heartbeat__":
            print "heartbeat received", msg

        if topic == "client_monitor_response":
            if payload == None:
                return
            if main:
                main.client_monitor_add_to_queue(payload[0],payload[2],payload[1])

    except Exception as e:
        print "exception in network_message_handler", e


def init(HOSTNAME):
    global main
    # global network
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
    network.subscribe_to_topic("found_beer")
    network.subscribe_to_topic("update_complete")
    network.subscribe_to_topic("image_capture_from_camera_unit")
    network.subscribe_to_topic("client_monitor_response")
    network.subscribe_to_topic("receive_image_overlay")
    network.subscribe_to_topic("receive_image_data")
    network.subscribe_to_topic("classification_data_to_conductor")


    main = Main(network)
    return main
