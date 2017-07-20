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
import csv
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
import pandas as pd
import sqlalchemy
import pymysql
from sqlalchemy import create_engine

from thirtybirds_2_0.Network.manager import init as network_init
from web_interface import WebInterface

CAPTURES_PATH = "/home/nvidia/supercooler/Captures/"

PARSED_CAPTURES_PATH = "/home/nvidia/supercooler/ParsedCaptures/"


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
        if parent_dir is None:
            mkdir_stdout = \
                subprocess.check_output(['gdrive', 'mkdir', new_dir])
        else:
            mkdir_stdout = \
                subprocess.check_output(['gdrive', 'mkdir', '-p', parent_dir, new_dir])
        return mkdir_stdout.split(" ")[1]

    def push_to_ab_db(self, simplest_inventory):
        try: 
            print simplest_inventory
            tm_door = time.strftime("%H:%M")
            dt_door = time.strftime("%e/%m/%y")
            #output from running main needs to be csv named data (from json sent previously, convert to csv using following code)
            #example dataset to push to aws
            #json_inventory_output = """[{"score": 0.990728, "shelf": "A", "duplicate": false, "camera": 6, "y": 116.61413043478262, "x": 351.0238095238095, "type": 3}, {"score": 0.993094, "shelf": "A", "duplicate": false, "camera": 9, "y": 302.31739130434784, "x": 198.1150793650794, "type": 3}, {"score": 0.991135, "shelf": "B", "duplicate": false, "camera": 2, "y": 3.7750000000000057, "x": 437.1190476190476, "type": 17}, {"score": 0.990654, "shelf": "B", "duplicate": false, "camera": 3, "y": 9.523913043478274, "x": 465.593253968254, "type": 17}, {"score": 0.985321, "shelf": "B", "duplicate": false, "camera": 4, "y": 208.32934782608692, "x": 190.04365079365078, "type": 7}, {"score": 0.991188, "shelf": "B", "duplicate": false, "camera": 6, "y": 132.6576086956522, "x": 443.8452380952381, "type": 17}, {"score": 0.991367, "shelf": "B", "duplicate": false, "camera": 7, "y": 138.8076086956522, "x": 475.45833333333337, "type": 17}, {"score": 0.991907, "shelf": "B", "duplicate": false, "camera": 7, "y": 71.55869565217392, "x": 467.3869047619048, "type": 17}, {"score": 0.987654, "shelf": "B", "duplicate": false, "camera": 9, "y": 334.8054347826087, "x": 230.1765873015873, "type": 5}, {"score": 0.994215, "shelf": "B", "duplicate": false, "camera": 10, "y": 221.29782608695655, "x": 448.55357142857144, "type": 2}, {"score": 0.990443, "shelf": "B", "duplicate": false, "camera": 10, "y": 278.6532608695652, "x": 451.468253968254, "type": 17}, {"score": 0.991464, "shelf": "B", "duplicate": false, "camera": 11, "y": 274.1076086956522, "x": 483.5297619047619, "type": 17}, {"score": 0.998189, "shelf": "C", "duplicate": false, "camera": 0, "y": -1.5728260869565247, "x": 147.22023809523813, "type": 2}, {"score": 0.998174, "shelf": "C", "duplicate": false, "camera": 0, "y": -2.107608695652175, "x": 196.54563492063488, "type": 2}, {"score": 0.998186, "shelf": "C", "duplicate": false, "camera": 0, "y": 7.785869565217382, "x": 91.39285714285722, "type": 2}, {"score": 0.998185, "shelf": "C", "duplicate": false, "camera": 1, "y": 37.065217391304344, "x": 233.98809523809524, "type": 2}, {"score": 0.998186, "shelf": "C", "duplicate": false, "camera": 1, "y": 6.181521739130446, "x": 209.99801587301585, "type": 2}, {"score": 0.998103, "shelf": "C", "duplicate": false, "camera": 2, "y": 49.365217391304355, "x": 465.593253968254, "type": 3}, {"score": 0.997359, "shelf": "C", "duplicate": false, "camera": 3, "y": 10.727173913043487, "x": 512.6765873015872, "type": 3}, {"score": 0.996092, "shelf": "C", "duplicate": false, "camera": 3, "y": 39.07065217391303, "x": 456.4007936507936, "type": 3}, {"score": 0.998192, "shelf": "C", "duplicate": false, "camera": 4, "y": 144.02173913043475, "x": 125.02380952380952, "type": 2}, {"score": 0.998183, "shelf": "C", "duplicate": false, "camera": 4, "y": 114.6086956521739, "x": 171.4345238095238, "type": 2}, {"score": 0.998181, "shelf": "C", "duplicate": false, "camera": 4, "y": 187.3391304347826, "x": 138.47619047619048, "type": 2}, {"score": 0.998161, "shelf": "C", "duplicate": false, "camera": 4, "y": 156.18804347826085, "x": 183.54166666666669, "type": 2}, {"score": 0.998185, "shelf": "C", "duplicate": false, "camera": 4, "y": 113.13804347826087, "x": 105.96626984126982, "type": 2}, {"score": 0.998193, "shelf": "C", "duplicate": false, "camera": 5, "y": 73.56413043478261, "x": 238.92063492063494, "type": 2}, {"score": 0.998184, "shelf": "C", "duplicate": false, "camera": 5, "y": 156.32173913043476, "x": 210.22222222222223, "type": 2}, {"score": 0.998188, "shelf": "C", "duplicate": false, "camera": 5, "y": 111.13260869565218, "x": 257.0813492063492, "type": 2}, {"score": 0.998191, "shelf": "C", "duplicate": false, "camera": 5, "y": 115.14347826086959, "x": 202.59920634920638, "type": 2}, {"score": 0.998521, "shelf": "C", "duplicate": false, "camera": 6, "y": 117.14891304347827, "x": 472.7678571428571, "type": 3}, {"score": 0.998743, "shelf": "C", "duplicate": false, "camera": 6, "y": 193.75652173913045, "x": 441.82738095238096, "type": 3}, {"score": 0.998496, "shelf": "C", "duplicate": false, "camera": 6, "y": 120.625, "x": 412.9047619047619, "type": 3}, {"score": 0.998747, "shelf": "C", "duplicate": false, "camera": 6, "y": 82.6554347826087, "x": 455.50396825396825, "type": 3}, {"score": 0.998688, "shelf": "C", "duplicate": false, "camera": 7, "y": 204.45217391304345, "x": 488.46230158730157, "type": 3}, {"score": 0.998741, "shelf": "C", "duplicate": false, "camera": 7, "y": 82.52173913043478, "x": 463.79960317460313, "type": 3}, {"score": 0.998715, "shelf": "C", "duplicate": false, "camera": 7, "y": 119.42173913043476, "x": 490.031746031746, "type": 3}, {"score": 0.998191, "shelf": "C", "duplicate": false, "camera": 8, "y": 250.04239130434786, "x": 128.61111111111114, "type": 2}, {"score": 0.963521, "shelf": "C", "duplicate": false, "camera": 9, "y": 240.55, "x": 231.07341269841265, "type": 5}, {"score": 0.998747, "shelf": "C", "duplicate": false, "camera": 10, "y": 250.30978260869563, "x": 445.19047619047615, "type": 3}, {"score": 0.9701, "shelf": "C", "duplicate": false, "camera": 10, "y": 256.19239130434784, "x": 432.6349206349206, "type": 14}, {"score": 0.995156, "shelf": "D", "duplicate": false, "camera": 0, "y": 4.176086956521729, "x": 157.3095238095238, "type": 16}, {"score": 0.994826, "shelf": "D", "duplicate": false, "camera": 1, "y": 8.721739130434784, "x": 221.65674603174602, "type": 16}, {"score": 0.995399, "shelf": "D", "duplicate": false, "camera": 2, "y": -1.0380434782608603, "x": 411.1111111111111, "type": 16}, {"score": 0.995051, "shelf": "D", "duplicate": false, "camera": 3, "y": 6.315217391304344, "x": 496.9821428571429, "type": 16}, {"score": 0.995362, "shelf": "D", "duplicate": false, "camera": 4, "y": 115.41086956521738, "x": 150.13492063492066, "type": 16}, {"score": 0.994977, "shelf": "D", "duplicate": false, "camera": 4, "y": 164.07608695652175, "x": 162.01785714285717, "type": 16}, {"score": 0.995415, "shelf": "D", "duplicate": false, "camera": 5, "y": 115.5445652173913, "x": 222.10515873015873, "type": 16}, {"score": 0.995005, "shelf": "D", "duplicate": false, "camera": 5, "y": 167.41847826086956, "x": 223.4503968253968, "type": 16}, {"score": 0.995322, "shelf": "D", "duplicate": false, "camera": 6, "y": 167.6858695652174, "x": 439.3611111111111, "type": 16}, {"score": 0.995453, "shelf": "D", "duplicate": false, "camera": 6, "y": 112.4695652173913, "x": 428.82341269841265, "type": 16}, {"score": 0.995424, "shelf": "D", "duplicate": false, "camera": 7, "y": 113.94021739130434, "x": 506.3988095238095, "type": 16}, {"score": 0.995271, "shelf": "D", "duplicate": false, "camera": 7, "y": 168.08695652173913, "x": 518.0575396825398, "type": 16}, {"score": 0.992517, "shelf": "D", "duplicate": false, "camera": 8, "y": 226.37826086956522, "x": 155.74007936507934, "type": 16}, {"score": 0.995239, "shelf": "D", "duplicate": false, "camera": 8, "y": 278.6532608695652, "x": 163.1388888888889, "type": 16}, {"score": 0.994071, "shelf": "D", "duplicate": false, "camera": 9, "y": 222.36739130434785, "x": 208.8769841269841, "type": 16}, {"score": 0.994748, "shelf": "D", "duplicate": false, "camera": 9, "y": 280.25760869565215, "x": 233.7638888888889, "type": 16}, {"score": 0.994834, "shelf": "D", "duplicate": false, "camera": 10, "y": 273.70652173913044, "x": 439.58531746031747, "type": 16}]"""
            #json_inventory_output = json.loads(json_inventory_output)
            csv_inventory_output = csv.writer(open("inventory.csv", "wb+"))
            csv_inventory_output.writerow(["sku_id", "tm_door", "dt_door", "num_instock"])

            for ab_id_key,  ab_id_value in simplest_inventory.items():
                inventory.writerow(
                        [
                            ab_id_key,
                            tm_door,
                            dt_door,
                            ab_id_value
                        ]
                )
            dataframe = pd.DataFrame.from_csv("inventory.csv")
            engine = create_engine("mysql+pymysql://root:password@historicoosdata.c4z0sx2tgyqk.us-east-2.rds.amazonaws.com:3306/HistoricOOSData")
            dataframe.to_sql('inventory', engine, if_exists='replace', index=False)
        except Exception as e:
            print "can't connect to db!"


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
        self.network.thirtybirds.send("reboot", "")
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

    def get_as_nparray(self, filename):
        return cv2.imread(os.path.join(self.capture_path, filename))

    def get_filepaths(self):
        filenames = self.get_filenames()
        return list(map((lambda filename:  os.path.join(self.capture_path, filename)), filenames))

    def get_filenames(self):
        return sorted([ filename for filename in os.listdir(self.capture_path) if filename.endswith(".png") ])


class Products(object):
    def __init__(self):
        self.products = {
            "bottlebecks":                      {"ab_id":"1", "height": 23,     "width":6,  "report_id": 1,  "confidence_threshold":0.95},
            "bottlebudamerica":            {"ab_id":"2", "height": 23,     "width":6,  "report_id": 2,  "confidence_threshold":0.95},
            "bottlebudlight":                  {"ab_id":"3", "height": 23,     "width":6,  "report_id": 3,  "confidence_threshold":0.95},
            "bottleplatinum":                 {"ab_id":"4", "height": 23,     "width":6,  "report_id": 4,  "confidence_threshold":0.95},
            "bottlecorona":                     {"ab_id":"5", "height": 24.5,  "width":6,  "report_id": 5,  "confidence_threshold":0.95},
            "bottlehoegaarden":            {"ab_id":"6", "height": 23,     "width":6,  "report_id": 6,  "confidence_threshold":0.95},
            "bottleultra":                        {"ab_id":"7", "height": 23,     "width":6,  "report_id": 7,  "confidence_threshold":0.95},
            "bottleshocktopraspberry":{"ab_id":"8", "height": 23,     "width":6,  "report_id": 8,  "confidence_threshold":0.95},
            "bottleshocktoppretzel":     {"ab_id":"9","height": 23,     "width":6,  "report_id": 9,  "confidence_threshold":0.95},
            "bottlestella":                       {"ab_id":"10","height": 23,     "width":6,  "report_id": 10,  "confidence_threshold":0.95},
            "canbudamerica12":            {"ab_id":"11","height": 12.5,  "width":5.3,  "report_id": 11,  "confidence_threshold":0.95},
            "canbudlight12":                  {"ab_id":"12","height": 12.5,  "width":5.3,  "report_id": 12,  "confidence_threshold":0.95},
            "canbusch12":                      {"ab_id":"13","height": 12.5,  "width":5.3,  "report_id": 13,  "confidence_threshold":0.95},
            "cannaturallight12":            {"ab_id":"15","height": 12.5,  "width":5.3,  "report_id": 15,  "confidence_threshold":0.95},
            "canbudice":                         {"ab_id":"17","height": 20.5,  "width":6.3,  "report_id": 17,  "confidence_threshold":0.95},
            "canbudice25":                    {"ab_id":"17","height": 25,  "width":6.3,  "report_id": 17,  "confidence_threshold":0.95},
            "canbudlight25":                 {"ab_id":"18","height": 25,  "width":6.3,  "report_id": 17,  "confidence_threshold":0.95},
            "canbudamerica25":           {"ab_id":"16","height": 25,  "width":6.3,  "report_id": 17,  "confidence_threshold":0.95},
            "negative":                           {"ab_id":"0","height": 0,        "width":0,  "report_id": 0,  "confidence_threshold":0}
        }


    def get_product_parameters(self):
        return  dict(self.products)

    def get_height(self, product_name):
        return self.products[product_name]["height"]

    def get_width(self, product_name):
        return self.products[product_name]["width"]

    def get_report_id(self, product_name):
        return self.products[product_name]["report_id"]

    def get_confidence_threshold(self, product_name):
        return self.products[product_name]["confidence_threshold"]

    def get_ab_id(self, product_name):
        return self.products[product_name]["ab_id"]

class Duplicate_Filter(object):
    def __init__(self, products):
        self.products = products
        self.clusters = []
        self.diameter_threshold = 80 # mm - that's a guess. verify
        self.confidence_threshold = 0.95
        self.shelf_ids = ['A','B','C','D']
        #self.confident_objects = []

        # global coordinate system
        self.x_max = 1000
        self.y_max = 1000

    # TODO: search for duplicates, transform to global coords & normalize
    def filter_and_transform(self, potential_objects):
        # for now, just go through list of potential objects + assign
        # normalized global coords at random
        objects_normalized_coords = []
        for i, potential_object in enumerate(potential_objects):
            objects_normalized_coords.append(potential_object.copy())
            objects_normalized_coords[i]['norm_x'] = random.uniform(0, self.x_max)
            objects_normalized_coords[i]['norm_y'] = random.uniform(0, self.y_max)

        return objects_normalized_coords

    def search_for_duplicates(self, potential_objects):
        #self.add_global_coords(potential_objects)
        self.confident_objects = self.filter_out_unconfident_objects(potential_objects)
        self.non_nested_objects = self.filter_out_spatially_nested_objects(self.confident_objects)

        # start with shelf x/y coordinates.  calculate here if neccessary
        for shelf_id in self.shelf_ids:
            for i, outer_confident_object in enumerate( confident_objects ):
                for j, inner_confident_object in  enumerate( confident_objects ):
                        if i != j:  # avoid comparing same potential_objects
                            distance  = self.calculate_distance(outer_confident_object['global_x'],outer_confident_object['global_y'],inner_confident_object['global_x'],inner_confident_object['global_y'])  # calculate proximity based on shelf-based coordinates, object diameter, elastic factor
                            if distance < self.diameter_threshold: # if objects are close
                                # if in clusters, add to cluster
                                # if not in cluters, create new cluster
                                # if objects are within duplicate range
                                # how to match with existing clusters?
                                pass



    def filter_out_spatially_nested_objects(self, superset_objects):
        #internal comparrison
        for shelf_id in self.shelf_ids:
            for camera_id in range(12):
                objects_from_single_camera = filter(lambda d: d['shelf_id'] == shelf_id and int(d['camera_id']) == camera_id,  superset_objects)
                for objects_from_single_camera_a, objects_from_single_camera_b in itertools.combinations(objects_from_single_camera, 2):
                    # todo: prevent comparing the same pairs of objects as switched inner/outer roles.  probably a looping solution
                    centroid_distance, radius_distance, radius_inside, centroid_inside = self.calculate_centroid_distance_and_radius_distance(
                        (objects_from_single_camera_a["camera_x"], objects_from_single_camera_a["camera_y"], objects_from_single_camera_a["radius"]), 
                        (objects_from_single_camera_b["camera_x"], objects_from_single_camera_b["camera_y"], objects_from_single_camera_b["radius"])
                    )
                    

    def calculate_centroid_distance_and_radius_distance(self, circle_a, circle_b ):
        centroid_distance = math.pow( math.pow(circle_a['x'] - circle_b['x'], 2) + math.pow(circle_a['y'] - circle_b['y'], 2), 0.5)
        circle_outer, inner_circle = circle_a, circle_b if circle_a['r'] > circle_b['r'] else circle_b, circle_a
        radius_distance =  circle_outer['r'] - (inner_circle['r'] + centroid_distance)
        radius_inside = True if radius_distance > 0 else False
        centroid_inside = True if radius_distance + inner_circle['r'] > 0 else False
        return  centroid_distance, radius_distance, radius_inside, centroid_inside


    def group_suspiciously_proximal_objects(self, objects):
        pass

    def add_global_coords(self, objects):
        pass

    def calculate_distance(self, outer_x, outer_y, inner_x, inner_y ):
        return math.sqrt( math.pow((outer_x-inner_x),  2) + math.pow((outer_y-inner_y),  2))



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

class Detected_Objects(object):
    def __init__(self, capture_path, parsed_capture_path, products):
        self.capture_path = capture_path
        self.parsed_capture_path = parsed_capture_path
        self.products = products
        self.potential_objects = []
        self.confident_objects = []
        self.shelf_ids = ['A','B','C','D']
        self.camera_range = range(12)

    def get_best_guess(self, detected_object):
        return detected_object["classification"][0] #list of items should arlready be sorted

    def shelf_camera_ids_generator(self):
        for s in self.shelf_ids:
            for c in range(12): 
                yield s, c

    def filter_object_list_by_shelf_and_camera(self, shelf_id, camera_id, object_list):
        return filter(lambda d: d['shelf_id'] == shelf_id and int(d['camera_id']) == camera_id,  object_list)

    def annotate_image(self, source_image_filepath, annotations, destination_image_filepath):
        #print "annotate_image", source_image_filepath, destination_image_filepath, annotations
        # this might fit better in another class
        # annotations format:
        # [ {"type":"", "data":{}}}]
        # [ {"type":"circle", "data":{"x":100,"y":200, "radius":20}]
        # [ {"type":"label" "data":{"x":100,"y":200, "text":"foo"}]
        source_image = cv2.imread(source_image_filepath)
        annotated_image = source_image.copy()
        for annotation in annotations:
            if annotation["type"] == "circle":
                cv2.circle(
                    annotated_image, 
                    (annotation["x"], annotation["y"]), 
                    annotation["radius"], 
                    annotation["color"], 
                    2
                )
            if annotation["type"] == "text":
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(
                    annotated_image,
                    annotation["text"],
                    (annotation["x"], annotation["y"]), 
                    font, 
                    0.5,
                    annotation["color"],
                    1
                )
        cv2.imwrite(destination_image_filepath, annotated_image)

    def create_potential_object_images(self, object_list):
        shelf_camera_iterator = self. shelf_camera_ids_generator()
        for shelf_id, camera_id in shelf_camera_iterator:
            print shelf_id, camera_id
            objects_from_one_camera =  self.filter_object_list_by_shelf_and_camera(shelf_id, camera_id, object_list)
            annotations = []
            for object_from_one_camera in objects_from_one_camera:
                print object_from_one_camera
                annotations.append(
                    {
                        "type":"circle", 
                        "x":object_from_one_camera["camera_x"], 
                        "y":object_from_one_camera["camera_y"], 
                        "radius":object_from_one_camera["radius"],
                        "color":(0, 255, 0)
                    }
                )
            source_image_filename = "{}_{}.png".format(shelf_id, camera_id)
            source_image_filepath = os.path.join(self.capture_path, source_image_filename)
            if  os.path.isfile(source_image_filepath): # this image should exist.  but roll with the case in which is doesn't
                destination_image_filename = "potentialObjects_{}_{}.png".format(shelf_id, camera_id)
                destination_image_filepath = os.path.join(self.parsed_capture_path, destination_image_filename)
                self.annotate_image(source_image_filepath, annotations, destination_image_filepath)
            else:
                print "Detected_Objects.create_potential_object_images image not found at", source_image_filepath

    def create_classified_object_images(self, object_list):
        shelf_camera_iterator = self. shelf_camera_ids_generator()
        for shelf_id, camera_id in shelf_camera_iterator:
            objects_from_one_camera =  self.filter_object_list_by_shelf_and_camera(shelf_id, camera_id, object_list)
            annotations = []
            for object_from_one_camera in objects_from_one_camera:
                product_name,  confidence = self.get_best_guess(object_from_one_camera)
                label = "{}({})".format(product_name,  confidence)
                if confidence < 0.9:
                    circle_color = (0, 127, 127) # yellow
                else:
                    if product_name == "negative":
                        circle_color = (0, 0, 255) # red
                    else:
                        circle_color = (0, 255, 0) # green
                annotations.append(
                    {
                        "type":"circle", 
                        "x":object_from_one_camera["camera_x"], 
                        "y":object_from_one_camera["camera_y"], 
                        "radius":object_from_one_camera["radius"],
                        "color":circle_color
                    }
                )
                annotations.append(
                    {
                        "type":"text", 
                        "x":object_from_one_camera["camera_x"], 
                        "y":object_from_one_camera["camera_y"], 
                        "text": label,
                        "color":circle_color
                    }
                )
            source_image_filename = "{}_{}.png".format(shelf_id, camera_id)
            source_image_filepath = os.path.join(self.capture_path, source_image_filename)
            if  os.path.isfile(source_image_filepath): # this image should exist.  but roll with the case in which is doesn't
                destination_image_filename = "classifiedObjects_{}_{}.png".format(shelf_id, camera_id)
                destination_image_filepath = os.path.join(self.parsed_capture_path, destination_image_filename)
                self.annotate_image(source_image_filepath, annotations, destination_image_filepath)
            else:
                print "Detected_Objects.create_classified_object_images image not found at", source_image_filepath

    def create_confident_object_images(self):
        shelf_camera_iterator = self. shelf_camera_ids_generator()
        for shelf_id, camera_id in shelf_camera_iterator:
            objects_from_one_camera =  self.filter_object_list_by_shelf_and_camera(shelf_id, camera_id, self.confident_objects)
            annotations = []
            for object_from_one_camera in objects_from_one_camera:
                product_name,  confidence = self.get_best_guess(object_from_one_camera)
                label = "{}({})".format(product_name,  confidence)
                circle_color = (0, 255, 0) # green
                annotations.append(
                    {
                        "type":"circle", 
                        "x":object_from_one_camera["camera_x"], 
                        "y":object_from_one_camera["camera_y"], 
                        "radius":object_from_one_camera["radius"],
                        "color":circle_color
                    }
                )
                annotations.append(
                    {
                        "type":"text", 
                        "x":object_from_one_camera["camera_x"], 
                        "y":object_from_one_camera["camera_y"], 
                        "text": label,
                        "color":circle_color
                    }
                )
            source_image_filename = "{}_{}.png".format(shelf_id, camera_id)
            source_image_filepath = os.path.join(self.capture_path, source_image_filename)
            if  os.path.isfile(source_image_filepath): # this image should exist.  but roll with the case in which is doesn't
                destination_image_filename = "confidentObjects_{}_{}.png".format(shelf_id, camera_id)
                destination_image_filepath = os.path.join(self.parsed_capture_path, destination_image_filename)
                self.annotate_image(source_image_filepath, annotations, destination_image_filepath)
            else:
                print "Detected_Objects.create_confident_object_images image not found at", source_image_filepath



        shelf_camera_iterator = self. shelf_camera_ids_generator()
        for shelf_id, camera_id in shelf_camera_iterator:
            objects_from_one_camera =  self.filter_object_list_by_shelf_and_camera(shelf_id, camera_id, object_list)
            annotations = []
            for object_from_one_camera in objects_from_one_camera:
                product_name,  confidence = self.get_best_guess(object_from_one_camera)
                label = "{}({})".format(product_name,  confidence)


    def add_product_parameters(self, detected_objects):
        for detected_object in detected_objects:
            detected_object["product"] = {}
            detected_object["product"]["name"], detected_object["product"]["confidence"] =   self.get_best_guess(detected_object)
            detected_object["product"]["height"] = self.products.get_height(detected_object["product"]["name"])
            detected_object["product"]["width"] = self.products.get_width(detected_object["product"]["name"])
            detected_object["product"]["report_id"] = self.products.get_report_id(detected_object["product"]["name"])
            detected_object["product"]["confidence_threshold"] = self.products.get_confidence_threshold(detected_object["product"]["name"])

    def filter_out_unconfident_objects(self, superset_objects):
        self.confident_objects =  filter(lambda superset_object: superset_object["product"]["name"] != "negative",   superset_objects )
        #self.confident_objects =  filter(lambda superset_object: superset_object["product"]["name"] != "negative"  and    superset_object["product"]["confidence"] >= superset_object["product"]["confidence_threshold"],   superset_objects )

    def add_real_world_coordinates(self):
        shelf_camera_iterator = self. shelf_camera_ids_generator()
        for shelf_id, camera_id in shelf_camera_iterator:
            objects_from_one_camera =  self.filter_object_list_by_shelf_and_camera(shelf_id, camera_id, self.confident_objects)
            for object_from_one_camera in objects_from_one_camera:
                object_from_one_camera["real_world_x"] = 0 # position in inches
                object_from_one_camera["real_world_y"] = 0 # position in inches

    def tabulate_inventory(self):
        inventory = {
            "0":0,
            "1":0,
            "2":0,
            "3":0,
            "4":0,
            "5":0,
            "6":0,
            "7":0,
            "8":0,
            "9":0,
            "10":0,
            "11":0,
            "12":0,
            "13":0,
            "14":0,
            "15":0,
            "16":0,
            "17":0,
            "18":0,
        }
        for confident_object in self.confident_objects:
            ab_id = self.products.get_ab_id(confident_object["name"])
            inventory[ab_id] += 1
        return inventory

    """
    def search_for_duplicates(self, potential_objects):

        # start with shelf x/y coordinates.  calculate here if neccessary
        for shelf_id in self.shelf_ids:
            for i, outer_confident_object in enumerate( confident_objects ):
                for j, inner_confident_object in  enumerate( confident_objects ):
                        if i != j:  # avoid comparing same potential_objects
                            distance  = self.calculate_distance(outer_confident_object['global_x'],outer_confident_object['global_y'],inner_confident_object['global_x'],inner_confident_object['global_y'])  # calculate proximity based on shelf-based coordinates, object diameter, elastic factor
                            if distance < self.diameter_threshold: # if objects are close
                                # if in clusters, add to cluster
                                # if not in cluters, create new cluster
                                # if objects are within duplicate range
                                # how to match with existing clusters?
                                pass



    def filter_out_spatially_nested_objects(self, superset_objects):
        #internal comparrison
        for shelf_id in self.shelf_ids:
            for camera_id in range(12):
                objects_from_single_camera = filter(lambda d: d['shelf_id'] == shelf_id and int(d['camera_id']) == camera_id,  superset_objects)
                for objects_from_single_camera_a, objects_from_single_camera_b in itertools.combinations(objects_from_single_camera, 2):
                    # todo: prevent comparing the same pairs of objects as switched inner/outer roles.  probably a looping solution
                    centroid_distance, radius_distance, radius_inside, centroid_inside = self.calculate_centroid_distance_and_radius_distance(
                        (objects_from_single_camera_a["camera_x"], objects_from_single_camera_a["camera_y"], objects_from_single_camera_a["radius"]), 
                        (objects_from_single_camera_b["camera_x"], objects_from_single_camera_b["camera_y"], objects_from_single_camera_b["radius"])
                    )
                    
    """





# Main handles network send/recv and can see all other classes directly
class Main(threading.Thread):
    def __init__(self, hostname):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()
        self.images_undistorted = Images(CAPTURES_PATH)
        self.products = Products()
        self.duplicate_filter = Duplicate_Filter(self.products)
        self.web_interface = WebInterface()
        self.inventory = Inventory()
        self.network = Network(hostname, self.network_message_handler, self.network_status_handler)
        self.gdrive_captures_directory = "0BzpNPyJoi6uoSGlhTnN5RWhXRFU"
        self.light_level = 7
        self.camera_capture_delay = 10
        self.object_detection_wait_period = 300
        self.whole_process_wait_period = 330
        self.soonest_run_time = time.time()
        self.camera_units = Camera_Units(self.network)
        self.response_accumulator = Response_Accumulator()
        self.detected_objects = Detected_Objects(CAPTURES_PATH, PARSED_CAPTURES_PATH, self.products)

        self.label_lines = [line.rstrip() for line 
            in tf.gfile.GFile("/home/nvidia/supercooler/Roles/jetson/tf_files/retrained_labels.txt")]

        with tf.gfile.FastGFile("/home/nvidia/supercooler/Roles/jetson/tf_files/retrained_graph.pb", 'rb') as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())

        with tf.Graph().as_default() as imported_graph:
            tf.import_graph_def(graph_def, name='')
            self.imported_graph = imported_graph

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
                    print shelf_id, camera_id
                    print potential_objects

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

                    self.detected_objects.create_potential_object_images(potential_objects)
                    print "OBJECT DETECTION COMPLETE"
                    
                    with tf.Session(graph=self.imported_graph) as sess:

                        for shelf_id in ['A','B','C','D']:
                            for camera_id in range(12):
                                potential_objects_subset = filter(lambda d: d['shelf_id'] == shelf_id and int(d['camera_id']) == camera_id,  potential_objects)
                                #print shelf_id, camera_id, potential_objects_subset

                                # if no objects were detected, skip
                                if len(potential_objects_subset) == 0: continue

                                # get undisotrted image and begin classification. use first object to grab shelf+cam
                                first_object = potential_objects_subset[0]
                                lens_corrected_img = self.images_undistorted.get_as_nparray(
                                    "{shelf_id}_{camera_id}.png".format(**first_object))

                                #with tf.Session() as sess:
                                self.crop_and_classify_images(potential_objects_subset, lens_corrected_img, sess)
                            #print potential_objects_subset
                    self.detected_objects.create_classified_object_images(potential_objects)

                    self.detected_objects.add_product_parameters(potential_objects)

                    self.detected_objects.filter_out_unconfident_objects(potential_objects)

                    self.detected_objects.create_confident_object_images()

                    simplest_inventory = self.detected_objects.tabulate_inventory()

                    self.network.push_to_ab_db(simplest_inventory)

                    # ----------- WEB INTERACE ---------------------------------------------------

                    # Filter out duplicates, return list of objects with normalized global coords
                    objects_for_web = self.duplicate_filter.filter_and_transform(potential_objects)

                    # prep for web interface (scale coordinates and lookup product ids) and send
                    web_interface.send_report(web_interface.prep_for_web(objects_for_web,
                        self.duplicate_filter.x_max, self.duplicate_filter.y_max))
                    
                    
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

    def reboot_system(self):
        # send reboot command to camera nodes + hardware controller
        print "sending reboot command to nodes..."
        self.camera_units.send_reboot()

        time.sleep(5)

        print "rebooting..."
        os.system("sudo reboot now")

    def crop_and_classify_images(self, potential_objects, image, sess, threshold=0.6):

        # if the best guess falls below this threshold, assume no match
        confidence_threshold = threshold

        print "crop_and_classify_images"
        
        for i, candidate in enumerate(potential_objects):

            # report progress every ten images
            if (i%10) == 0:
                print 'processing %dth image' % i
                time.sleep(1)

            # crop image and encode as jpeg (classifier expects jpeg)
            print "cropping..."

            r  = candidate['radius']
            (img_height, img_width) = image.shape[:2]

            x1 = max(candidate['camera_x']-r, 0)
            y1 = max(candidate['camera_y']-r, 0)
            x2 = min(x1 + r*2, img_width )
            y2 = min(y1 + r*2, img_height)

            img_crop = image[y1:y2, x1:x2]
            img_jpg = cv2.imencode('.jpg', img_crop)[1].tobytes()

            print "cropped image, w,h = ", x2-x1, y2-y1

            # get a list of guesses w/ confidence in this format:
            # guesses = [(best guess, confidence), (next guess, confidence), ...]
            print "running classifier..."

            guesses = self.guess_image(sess, img_jpg)
            best_guess, confidence = guesses[0]

            candidate["classification"] = guesses

            print guesses

    def guess_image(self, tf_session, image):
        # Feed the image_data as input to the graph and get first prediction
        softmax_tensor = tf_session.graph.get_tensor_by_name('final_result:0')
        
        print "run tf session..."
        predictions = tf_session.run(softmax_tensor, {'DecodeJpeg/contents:0': image})
        
        # Sort to show labels of first prediction in order of confidence
        print "sort labels.."
        top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]

        scores = [(self.label_lines[node_id], predictions[0][node_id]) for node_id in top_k]
        return scores


def init(hostname):
    main = Main(hostname)
    main.daemon = True
    main.start()
    return main


