"""
jetson is the puppetmaster.

    it :
0) Manages Thirtybirds networking and the client monitor
1) listens for door events
2) publishes messages to supercooler-hardware to set  light levels 
3) publishes messages to camera units to take captures
4) publishes messages to camera units to  process captures and report object detection
5) waits for camera units to return images 
6) performs image classification
7) identifies and removes duplicates
8) collates inventory
9) sends the inventory to EC2 interface.


"""
import base64
import cv2
import json
import math
import numpy as np
import os
import Queue
import subprocess
import tensorflow as tf
import time
import threading
import traceback
import settings
import signal
import sys
import yaml

import classifier
from thirtybirds_2_0.Network.manager import init as network_init
from web_interface import WebInterface

CAPTURES_PATH = "/home/nvidia/supercooler/Captures/"


class Network(object):
    def __init__(self, hostname, network_message_handler, network_status_handler):
        self.hostname = hostname
        self.thirtybirds = network_init(
            hostname=hostname,
            role="server",
            discovery_multicastGroup=settings.discovery_multicastGroup,
            discovery_multicastPort=settings.discovery_multicastPort,
            discovery_responsePort=settings.discovery_responsePort,
            pubsub_pubPort=settings.pubsub_pubPort,
            message_callback=network_message_handler,
            status_callback=network_status_handler
        )
    def copy_to_gdrive(self, google_drive_directory_id, filepath):
        try:
            subprocess.Popen(['gdrive', 'upload', '-p', google_drive_directory_id, filepath])
        except Exception as e:
            print "exception in Network.copy_to_gdrive", e

    def make_directory_on_gdrive(self, parent_dir, new_dir):
        if parent_dir == None:
            mkdir_stdout = \
                subprocess.check_output(['gdrive', 'mkdir', new_dir])
        else:
            mkdir_stdout = \
                subprocess.check_output(['gdrive', 'mkdir', '-p', parent_dir, new_dir])
        return mkdir_stdout.split(" ")[1]


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
            print "%s: %s : %s: %s: %s" % (hostname, self.hosts[hostname]["present"], self.hosts[hostname]["timestamp"], self.hosts[hostname]["pickle_version"], self.hosts[hostname]["git_pull_date"])

    def run(self):
        previous_hosts = {}
        while True:
            self.empty_host_list()
            self.network.thirtybirds.send("client_monitor_request", "")
            time.sleep(self.update_period)
            while not self.queue.empty():
                [hostname, git_pull_date, pickle_version, timestamp] = self.queue.get(True)
                #print ">>", hostname, git_pull_date, pickle_version, timestamp
                self.hosts[hostname]["present"] = True
                self.hosts[hostname]["timestamp"] = timestamp
                self.hosts[hostname]["pickle_version"] = pickle_version
                self.hosts[hostname]["git_pull_date"] = git_pull_date
            #if not cmp(previous_hosts,self.hosts):
            #    self.print_current_clients()
            #previous_hosts = self.hosts
            self.print_current_clients()


class Camera_Units(object):
    def __init__(self, network):
            self.network = network
    def capture_image(self, light_level_sequence_position, timestamp):
        self.network.thirtybirds.send("capture_image", (light_level_sequence_position, timestamp))
    def process_images_and_report(self):
        self.network.thirtybirds.send("process_images_and_report", "")
    def send_update_command(self, cool=False, birds=False, update=False, upgrade=False):
        self.network.thirtybirds.send("remote_update", [cool, birds, update, upgrade])
    def send_update_scripts_command(self):
        self.network.thirtybirds.send("remote_update_scripts", "")
    def send_reboot(self):
        self.network.thirtybirds.send("reboot")
    def return_raw_images(self):
        self.network.thirtybirds.send("return_raw_images", "")

class Images(object): 
    def __init__(self, capture_path):
        self.capture_path = capture_path

    def store(self, filename, binary_image_data):
        with open(os.path.join(self.capture_path, filename),'wb') as f:
            f.write(binary_image_data)

    def clear(self):
        previous_filenames = self.get_filenames()
        for previous_filename in previous_filenames:
            os.remove("{}{}".format(self.capture_path,  previous_filename))

    def get(self, filename):
        pass

    def get_filepaths(self):
        filenames = self.get_filenames()
        return list(map((lambda filename:  os.path.join(self.capture_path, filename)), filenames))

    def get_filenames(self):
        return [ filename for filename in os.listdir(self.capture_path) if filename.endswith(".png") ]


class Beers(object):
    def __init__(self):
        self.label_lookup = {
            "bottlebecks"               : 1,
            "bottlebudamerica"          : 2,
            "bottlebudlight"            : 3,
            "bottleplatinum"            : 4,
            "bottlecorona"              : 5,
            "bottlehoegaarden"          : 6,
            "bottleultra"               : 7,
            "bottleshocktopraspberry"   : 8,
            "bottleshocktoppretzel"     : 9,
            "bottlestella"              : 107,
            "canbudamerica"             : 11,
            "canbudlight"               : 12,
            "canbusch"                  : 13,
            "canbusch"                  : 14,
            "cannaturallight"           : 15,
            "canbudamerica"             : 16,
            "canbudice"                 : 17,
            "canbudlight"               : 18
        }
        self.product_specific_confidence_thresholds = {
            "bottlebecks"               : 0.99,
            "bottlebudamerica"     : 0.99,
            "bottlebudlight"           : 0.99,
            "bottleplatinum"          : 0.99,
            "bottlecorona"             : 0.95,
            "bottlehoegaarden"     : 0.99,
            "bottleultra"                 : 0.98,
            "bottleshocktopraspberry"   : 0.99,
            "bottleshocktoppretzel"        : 0.98,
            "bottlestella"                : 0.99,
            "canbudamerica"         : 0.95,
            "canbudlight"               : 0.99,
            "canbusch"                  : 0.94,
            "cannaturallight"         : 0.95,
            "canbudamerica"        : 0.99,
            "canbudice"                 : 0.99,
            "canbudlight"               : 0.99
        }

class Duplicate_Filter(object):
    def __init__(self, beers):
        self.beers = beers
        self.clusters = []
        self.diameter_threshold = 80 # mm - that's a guess. verify
    def search_for_duplicates(self, potential_objects):
        self.add_global_coords(potential_objects)
        confident_objects = self.filter_confident_objects(potential_objects)
        # start with shelf x/y coordinates.  calculate here if neccessary
        for shelf_id in ['A','B','C','D']:
            for i, outer_confident_object in enumerate( confident_objects ):
                for j, inner_confident_object in  enumerate( confident_objects ):
                        if i != j;  # avoid comparing same potential_objects
                            distance  = self.calculate_distance(outer_confident_object['global_x'],outer_confident_object['global_y'],inner_confident_object['global_x'],inner_confident_object['global_y'])  # calculate proximity based on shelf-based coordinates, object diameter, elastic factor
                            if distance < self.diameter_threshold: # if objects are close
                                # if in clusters, add to cluster
                                # if not in cluters, create new cluster
                                # if objects are within duplicate range
                                # how to match with existing clusters?

    def add_global_coords(self, objects):
        pass

    def filter_confident_objects(self,  objects):
        return objects

    def calculate_distance(self, outer_x, outer_y, inner_x, inner_y ):
        return math.sqrt( math.pow((outer_x-inner_x),  2) + math.pow((outer_y-inner_y),  2))

    def identity_same_camera_nested_objects(self, objects):
        # if camera is same
        # 
        pass


class Inventory(object):
    def __init__(self):
            pass

class Response_Accumulator(object):
    def __init__(self):
        self.potential_objects = []
        self.response_status = {
            "A":[False]*12,
            "B":[False]*12,
            "C":[False]*12,
            "D":[False]*12
        }
    def clear_potential_objects(self):
        self.potential_objects = []
        self.response_status = {
            "A":[False]*12,
            "B":[False]*12,
            "C":[False]*12,
            "D":[False]*12
        }
    def add_potential_objects(self, shelf_id, camera_id, potential_objects, print_status = False):
        self.response_status[shelf_id][camera_id] = True
        self.potential_objects.extend(potential_objects)
        if print_status:
            self.print_response_status()
    def print_response_status(self):
        print "Response_Accumulator"
        print "D", map(lambda status: "X" if status else " ", self.response_status["D"])
        print "C", map(lambda status: "X" if status else " ", self.response_status["C"])
        print "B", map(lambda status: "X" if status else " ", self.response_status["B"])
        print "A", map(lambda status: "X" if status else " ", self.response_status["A"])
        print "received", len(self.potential_objects), "potential objects"
    def get_potential_objects(self):
        return self.potential_objects

# Main handles network send/recv and can see all other classes directly
class Main(threading.Thread):
    def __init__(self, hostname):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        self.images_undistorted = Images(CAPTURES_PATH)
        self.beers = Beers()
        self.duplicate_filter = Duplicate_Filter(self.beers)
        self.web_interface = WebInterface()
        self.inventory = Inventory()
        self.network = Network(hostname, self.network_message_handler, self.network_status_handler)
        self.gdrive_captures_directory = "0BzpNPyJoi6uoSGlhTnN5RWhXRFU"
        self.light_level = 10
        self.camera_capture_delay = 10
        self.object_detection_wait_period = 240
        self.whole_process_wait_period = 300
        self.soonest_run_time = time.time()
        self.camera_units = Camera_Units(self.network)
        self.response_accumulator = Response_Accumulator()

        self.hostnames = [
            "supercoolerA0","supercoolerA1","supercoolerA2","supercoolerA3","supercoolerA4","supercoolerA5","supercoolerA6","supercoolerA7","supercoolerA8","supercoolerA9","supercoolerA10","supercoolerA11",
            "supercoolerB0","supercoolerB1","supercoolerB2","supercoolerB3","supercoolerB4","supercoolerB5","supercoolerB6","supercoolerB7","supercoolerB8","supercoolerB9","supercoolerB10","supercoolerB11",
            "supercoolerC0","supercoolerC1","supercoolerC2","supercoolerC3","supercoolerC4","supercoolerC5","supercoolerC6","supercoolerC7","supercoolerC8","supercoolerC9","supercoolerC10","supercoolerC11",
            "supercoolerD0","supercoolerD1","supercoolerD2","supercoolerD3","supercoolerD4","supercoolerD5","supercoolerD6","supercoolerD7","supercoolerD8","supercoolerD9","supercoolerD10","supercoolerD11",
            "supercooler-hardware"
        ]
        self.client_monitor_server = Thirtybirds_Client_Monitor_Server(self.network, self.hostnames)
        self.client_monitor_server.daemon = True
        self.client_monitor_server.start()

        self.network.thirtybirds.subscribe_to_topic("door_closed")
        self.network.thirtybirds.subscribe_to_topic("door_opened")
        self.network.thirtybirds.subscribe_to_topic("client_monitor_response")
        self.network.thirtybirds.subscribe_to_topic("receive_image_data")
        #self.network.subscribe_to_topic("system")  # subscribe to all system messages
        #self.network.subscribe_to_topic("update_complete")
        #self.network.subscribe_to_topic("image_capture_from_camera_unit")
        #self.network.subscribe_to_topic("receive_image_overlay")
        #self.network.subscribe_to_topic("classification_data_to_conductor")


    def network_message_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main
        topic, msg =  topic_msg # separating just to eval msg.  best to do it early.  it should be done in TB.
        if topic not in  ["client_monitor_response"]:
            print "Main.network_message_handler", topic
        if len(msg) > 0: 
            msg = eval(msg)
        self.add_to_queue(topic, msg)

    def network_status_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main
        print "Main.network_status_handler", topic_msg

    def add_to_queue(self, topic, msg):
        self.queue.put((topic, msg))

    def run(self):
        while True:
            try:
                topic, msg = self.queue.get(True)
                if topic not in ["client_monitor_response"]:
                    print "Main.run", topic
                if topic == "client_monitor_response":
                    self.client_monitor_server.add_to_queue(msg[0],msg[2],msg[1])
                if topic == "door_closed":
                    self.web_interface.send_door_close()

                    if time.time() >= self.soonest_run_time:
                        self.soonest_run_time = time.time() + self.whole_process_wait_period
                        timestamp = time.strftime("%Y-%m-%d-%H-%M-%S")
                        #dir_captures_now = self.network.make_directory_on_gdrive(self.gdrive_captures_directory, 'captures_' + timestamp)
                        #dir_unprocessed = self.network.make_directory_on_gdrive(dir_captures_now, 'unprocessed')
                        #dir_annotated = self.network.make_directory_on_gdrive(dir_captures_now, 'annotated')
                        #dir_parsed = self.network.make_directory_on_gdrive(dir_captures_now, 'parsed')
                        self.network.thirtybirds.send("set_light_level", self.light_level)
                        time.sleep(1)
                        self.camera_units.capture_image(self.light_level, timestamp)
                        time.sleep(self.camera_capture_delay)
                        self.network.thirtybirds.send("set_light_level", 0)
                        self.response_accumulator.clear_potential_objects()
                        self.images_undistorted.clear()
                        time.sleep(self.camera_capture_delay)
                        object_detection_timer = threading.Timer(self.object_detection_wait_period, self.add_to_queue, ("object_detection_complete",""))
                        object_detection_timer.start()
                        self.camera_units.process_images_and_report()
                    else:
                        print "too soon.  next available run time:", self.soonest_run_time
                if topic == "door_opened":
                    self.web_interface.send_door_open()
                if topic == "receive_image_data":
                    shelf_id =  msg["shelf_id"]
                    camera_id =  int(msg["camera_id"])
                    potential_objects =  msg["potential_objects"]

                    undistorted_capture_png = msg["undistorted_capture_ocv"]

                    # decode image to test classifier                    
                    nparr = np.fromstring(undistorted_capture_png, np.uint8)
                    undistorted_capture_ocv = cv2.imdecode(nparr, cv2.CV_LOAD_IMAGE_COLOR)
                    #classifier.classify_images(potential_objects, undistorted_capture_ocv)

                    self.response_accumulator.add_potential_objects(shelf_id, camera_id, potential_objects, True)
                    filename = "{}_{}.png".format(shelf_id, camera_id)
                    self.images_undistorted.store(filename, undistorted_capture_png)
                    
                if topic == "object_detection_complete":
                    print "OBJECT DETECTION COMPLETE ( how's my timing? )"
                    print self.response_accumulator.print_response_status()
                    print self.images_undistorted.get_filenames()
                    potential_objects = self.response_accumulator.get_potential_objects()
                    for shelf_id in ['A','B','C','D']:
                        for camera_id in range(12): 
                            potential_objects_subset = filter(lambda d: d['shelf_id'] == shelf_id and int(d['camera_id']) == camera_id,  potential_objects)
                            print shelf_id, camera_id, potential_objects_subset



            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))


def init(hostname):
    main = Main(hostname)
    main.daemon = True
    main.start()
    return main


