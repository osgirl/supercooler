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

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
DEVICES_PATH = "%s/Hosts/" % (BASE_PATH )
THIRTYBIRDS_PATH = "%s/thirtybirds" % (UPPER_PATH )

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)

class Main(threading.Thread):
    def __init__(self, hostname):
        threading.Thread.__init__(self)
        self.hostname = hostname

        ### NETWORK ###


        ### SET UP SUBSCRIPTIONS AND LISTENERS ###


        ### SET UP ATTAR ### so any exceptions can be reported


        ### CONNECT TO CAMERA ###   


        ###  ###









def init(hostname):
    main = Main(hostname)


