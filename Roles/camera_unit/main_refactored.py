
import base64
import commands
import cv2
import importlib
import json
from operator import itemgetter
import os
import Queue
import random
import settings 
import sys
import subprocess
import threading
import time

from thirtybirds_2_0.Network.manager import init as thirtybirds_network
from thirtybirds_2_0.Network.email_simple import init as email_init
from thirtybirds_2_0.Adaptors.Cameras.elp import init as camera_init
from thirtybirds_2_0.Updates.manager import init as updates_init
from thirtybirds_2_0.Network.info import init as network_info_init

#from parser import Image_Parser

#from watson_developer_cloud import VisualRecognitionV3

network_info = network_info_init()

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
DEVICES_PATH = "%s/Hosts/" % (BASE_PATH )
THIRTYBIRDS_PATH = "%s/thirtybirds" % (UPPER_PATH )

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)

########################
## OBJECT DETECTION
########################

#class Object_Detection(threading.Thread):
#    def __init__(self, hostname, network):
#        threading.Thread.__init__(self)

########################
## UTILS
########################

class Utils(object):
    def __init__(self, hostname):
        self.hostname = hostname
    def reboot(self):
        os.system("sudo reboot now")

    def get_shelf_id(self):
        return self.hostname[11:][:1]

    def get_camera_id(self):
        return self.hostname[12:]

    def create_image_file_name(self, timestamp, light_level, process_type):
        return "{}_{}_{}_{}_{}.png".format(timestamp, self.get_shelf_id() ,  self.get_camera_id(), light_level, raw_or_processed) 

    def remote_update_git(self, supercooler, thirtybirds, update, upgrade):
        if supercooler:
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/supercooler')
        if thirtybirds:
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/thirtybirds_2_0')
        return 

    def remote_update_scripts(self):
        updates_init("/home/pi/supercooler", False, True)
        return

    def get_pickle_version(self):
        (updates, ghStatus, bsStatus) = updates_init("/home/pi/supercooler", False, False)
        return updates.read_version_pickle()

    def get_git_timestamp(self):
        return commands.getstatusoutput("cd /home/pi/supercooler/; git log -1 --format=%cd")[1]   

    def get_client_status(self):
        return (self.hostname, self.get_pickle_version(), self.get_git_timestamp())
        self.network.send("client_monitor_response", (self.hostname,pickle_version, git_timestamp))


########################
## IMAGES
########################

class Images(object):
    def __init__(self, capture_path):
        self.capture_path = capture_path
        self.camera = camera_init(self.capture_path)

    def capture_image(self, filename):
        self.camera.take_capture(filename)

    def delete_captures(self):
        previous_filenames = [ previous_filename for previous_filename in os.listdir(self.capture_path) if previous_filename.endswith(".png") ]
        for previous_filename in previous_filenames:
            os.remove("{}{}".format(self.capture_path,  previous_filename))

    def get_values_from_filename(self, filename):
        shelf_id = filename[:-4][:1]
        camera_id = filename[1:-6]
        light_level = filename[:-8][-1:]
        return shelf_id, camera_id, light_level

    def get_current_capture_names(self):
        return [ os.path.join(self.capture_path, current_filename) for current_filename in os.listdir(self.capture_path) if current_filename.endswith(".png") ]


########################
## NETWORK
########################

class Network(object):
    def __init__(self, hostname, network_message_handler, network_status_handler):
        self.hostname = hostname
        self.thirtybirds = thirtybirds_network(
        hostname=hostname,
        role="client",
        discovery_multicastGroup=settings.discovery_multicastGroup,
        discovery_multicastPort=settings.discovery_multicastPort,
        discovery_responsePort=settings.discovery_responsePort,
        pubsub_pubPort=settings.pubsub_pubPort,
        message_callback=network_message_handler,
        status_callback=network_status_handler
    )
    def copy_to_gdrive(self, google_drive_directory_id, filepath):
        try:
            subprocess.call(['gdrive', 'upload', '-p', google_drive_directory_id, filepath])
        except Exception as e:
            print "exception in Network.copy_to_gdrive", e
                

########################
## DATA 
########################

class Data(threading.Thread):
    def __init__(self, hostname, network):
        threading.Thread.__init__(self)

#collate_classifcation_metadata

#create_object_metadata

#parse_and_annotate_images

########################
## MAIN
########################

class Main(threading.Thread):
    def __init__(self, hostname):
        threading.Thread.__init__(self)
        self.hostname = hostname
        self.capture_path = "/home/pi/supercooler/Captures/"
        self.parsed_capture_path = "/home/pi/supercooler/ParsedCaptures/"
        self.queue = Queue.Queue()
        self.network = Network(hostname, self.network_message_handler, self.network_status_handler)
        self.utils = Utils(hostname)
        self.images = Images(self.capture_path)

        self.network.thirtybirds.subscribe_to_topic("reboot")
        self.network.thirtybirds.subscribe_to_topic("remote_update")
        self.network.thirtybirds.subscribe_to_topic("remote_update_scripts")
        self.network.thirtybirds.subscribe_to_topic("capture_image")
        self.network.thirtybirds.subscribe_to_topic("client_monitor_request")
        self.network.thirtybirds.subscribe_to_topic("capture_and_upload")
        self.network.thirtybirds.subscribe_to_topic("perform_object_detection")
        #self.network.thirtybirds.subscribe_to_topic("process_images_and_report")
        #self.network.thirtybirds.subscribe_to_topic(HOSTNAME)
        #self.network.thirtybirds.subscribe_to_topic("return_raw_images")
        #self.network.thirtybirds.subscribe_to_topic("parse_and_annotate")
        #self.camera = camera_init(self.capture_path)

    def network_message_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main
        print "Main.network_message_handler", topic_msg
        topic, msg =  topic_msg # separating just to eval msg.  best to do it early.  it should be done in TB.
        if msg != "": msg == eval(msg)
        self.add_to_queue(topic, msg)

    def network_status_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main
        print "Main.network_status_handler", topic_msg

    def add_to_queue(self, topic, msg):
        self.queue.put((topic, msg))

    def run(self):
        while True:
            topic, msg = self.queue.get(True)

            if topic == "reboot":
                self.utils.reboot()

            if topic == "remote_update":
                supercooler, thirtybirds, update, upgrade = msg
                utils.remote_update_git(supercooler, thirtybirds, update, upgrade)
                self.network.thirtybirds.send("update_complete", self.hostname)

            if topic == "remote_update_scripts":
                self.utils.remote_update_scripts()
                self.network.thirtybirds.send("update_complete", self.hostname)

            if topic == "capture_image":
                light_level, timestamp = eval(msg)
                if light_level in [0, "0"]: # on request 0, empty directory
                    self.images.delete_captures()
                filename = utils.create_image_file_name(self, timestamp, light_level, "raw")
                self.images.capture_image(filename)

            if topic == "client_monitor_request":
                self.network.send("client_monitor_response", self.utils.get_client_status())

            if topic == "capture_and_upload":
                timestamp, light_level, google_drive_directory_id, clear_dir = msg
                if clear_dir: self.images.delete_captures()
                self.images.capture_image(utils.create_image_file_name(timestamp, light_level, "raw"))
                self.network.copy_to_gdrive(google_drive_directory_id, os.path.join(self.capture_path, filename))

            if topic == "perform_object_detection":
              pass  

            #if topic == "process_images_and_report":
            #if topic == self.hostname:
            #if topic == "return_raw_images":
            #if topic == "capture_and_upload":
            #if topic == "parse_and_annotate":


########################
## INIT
########################

def init(HOSTNAME):
    main = Main(HOSTNAME)
    main.daemon = True
    main.start()
    return main
