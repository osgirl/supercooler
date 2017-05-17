"""
TASKS:
    init:
        open reverse SSH connection to server

        listen to temp sensor
        listen to door sensor

    runtime:
        control lights

        send API messages to control camera_unit imaging processing
        receive processed capture
        receive inventory for each camera_unit ( including coordinates )
        confirm receipt of all captures and inventories
        
        disambiguate product identies
        produce inventory and map for bottles and cans

        undistort and stitch captures to create full image of each shelf
        parse capture for cases
        classify parses images
        create inventory and map for cases

        track time of last image cycle

        send report to server

API for camera_units:
    [ thirtybirds network stuff ]

API for Dashboard:
    pull

    push
        all attar data
"""
import time
import threading
import settings
import yaml
import json

from thirtybirds_2_0.Logs.main import Exception_Collector
from thirtybirds_2_0.Network.manager import init as network_init

def request_beer_over_and_over():
    threading.Timer(60, request_beer_over_and_over).start()
    request_beer()

def request_beer(hostname=None):
    topic = "get_beer_" + hostname if hostname != None else "get_beer"
    network.send(topic, "")

def network_status_handler(msg):
    print "network_status_handler", msg

def network_message_handler(msg):
    try:
        print "network_message_handler", msg
        topic = msg[0]
        #print "topic", topic 
        if topic == "__heartbeat__":
            print "heartbeat received", msg

        elif topic == "found_beer"
            print "got beer", eval(msg)

    except Exception as e:
        print "exception in network_message_handler", e

network = None

def init(HOSTNAME):
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
    #network.subscribe_to_topic("sensor_data")  
    #network.subscribe_to_topic("cell_data")
    #network.subscribe_to_topic("incubator_data")
    #network.subscribe_to_topic("algorithm_data")
    
    network.subscribe_to_topic("found_beer")

    request_beer_over_and_over()