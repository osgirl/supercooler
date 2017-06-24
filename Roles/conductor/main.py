"""

"""

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

# use wiringpi for software PWM
import wiringpi as wpi

import tensorflow as tf
import numpy as np

class Door(threading.Thread):
    def __init__(self, door_close_event_callback, door_open_event_callback):
        threading.Thread.__init__(self)
        self.closed = True
        self.door_pin_number = 29
        self.last_closure = time.time()
        self.door_close_event_callback = door_close_event_callback
        self.door_open_event_callback = door_open_event_callback
        # use pin 29 as door sensor (active LOW)
        wpi.pinMode(self.door_pin_number, wpi.INPUT)
        wpi.pullUpDnControl(self.door_pin_number, wpi.PUD_UP)

    def run(self):
        while True:
            closed_temp =  not wpi.digitalRead(self.door_pin_number)
            if self.closed != closed_temp:
                print "Door.run self.closed=", self.closed
                self.closed = closed_temp
                if self.closed:
                    self.door_close_event_callback()
                else: 
                    self.door_open_event_callback()
            time.sleep(0.5)

class Lights():
    def __init__(self):
        self.pwm_pins = [21, 22, 23, 24]
        self.light_sequence_levels = [ 10, 5, 0]
        for pwm_pin in self.pwm_pins:
            wpi.pinMode(pwm_pin, wpi.OUTPUT)
            wpi.softPwmCreate(pwm_pin, 0, 10)

    def set_level_shelf(self, id, value):
        wpi.softPwmWrite(self.pwm_pins[id], value)

    def set_level_all(self, value):
        for shelf_id in range(4):
            self.set_level_shelf(shelf_id, value)

    def play_sequence_step(self, step):
        self.set_level_all(self.light_sequence_levels[step])

    def play_test_sequence(self):
        for j in xrange(-10, 11):
            for i in xrange(4): self.set_level_shelf(i, 10 - abs(j))
            wpi.delay(200)

    def all_off(self):
        for i in xrange(4): self.set_level_shelf(i, 0) # turn off the lights

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
    #def ping_nodes_go(self):
    #   self.network.send("say_hello_to_node")

class Images():
    def __init__(self):
        # self.capture_path = "/home/pi/supercooler/Captures/"
        # self.dir_classify = "/home/pi/supercooler/Captures/"
        # self.dir_stitch = "/home/pi/supercooler/Captures_Stitching/"
        self.captures = []
        self.cropped_captures = []

    def receive_and_save(self, filename, raw_data):
        file_path = "{}{}".format(self.capture_path,filename)
        print "receive_and_save", file_path
        image_64_decode = base64.decodestring(raw_data) 
        image_result = open(file_path, 'wb') # create a writable image and write the decoding result
        image_result.write(image_64_decode)

    # def clear_captures(self):
    #     previous_filenames = [ previous_filename for previous_filename in os.listdir(self.capture_path) if previous_filename.endswith(".png") ]
    #     for previous_filename in previous_filenames:
    #         os.remove(   "{}{}".format(self.capture_path,  previous_filename) )

    def receive_image_data(self, payload):

        # decode and store image as numpy array
        img_arr = np.fromstring(base64.decodestring(payload["image"]), np.uint8)
        img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
        self.captures.append(img)
        index = len(self.captures) - 1    # store reference to index for crops

        # iterate through list of image bounds, store cropped capture info
        for i, bounds in enumerate(payload["bounds"]):
            cropped_capture = {
              "camera_id"   : payload["camera_id"],
              "shelf_id"    : payload["camera_id"][0],
              "light_level" : payload["light_level"],
              "img_index"   : index,
              "bounds"      : bounds
            }
            self.cropped_captures.append(cropped_capture)

images = Images()

class Thirtybirds_Client_Monitor_Server(threading.Thread):
    def __init__(self, network, hostnames, update_period=120):
        print "------ 1"
        threading.Thread.__init__(self)
        print "------ 2"
        self.update_period = update_period
        print "------ 3"
        self.current_clients = {}
        print "------ 4"
        self.remembered_clients = {}
        print "------ 5"
        self.network = network
        print "------ 6"
        self.hostnames = hostnames
        print "------ 7"
        self.queue = Queue.Queue()
        print "------ 8"
        self.hosts = {}
        print "------ 9"

    def empty_host_list(self):
        print "empty_host_list 0"
        self.hosts = {}
        print "empty_host_list 1"
        for hostname in self.hostnames:
            print "empty_host_list 2", hostname
            self.hosts[hostname] = {
                "present":False,
                "timestamp":False,
                "pickle_version":False,
                "git_pull_date":False
            }
        print "empty_host_list 3"

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
            print "Thirtybirds_Client_Monitor_Server 1"
            self.network.send("client_monitor_request", "")
            print "Thirtybirds_Client_Monitor_Server 2"
            time.sleep(self.update_period)
            print "Thirtybirds_Client_Monitor_Server 3"
            while not self.queue.empty():
                [hostname, git_pull_date, pickle_version, timestamp] = self.queue.get(True)
                #print ">>", hostname, git_pull_date, pickle_version, timestamp
                self.hosts[hostname]["present"] = True
                self.hosts[hostname]["timestamp"] = timestamp
                self.hosts[hostname]["pickle_version"] = pickle_version
                self.hosts[hostname]["git_pull_date"] = git_pull_date
            print "Thirtybirds_Client_Monitor_Server 4"
            self.print_current_clients()
            print "Thirtybirds_Client_Monitor_Server  5"

print "<<<< 1"
hostnames = [
    "supercoolerA0","supercoolerA1","supercoolerA2","supercoolerA3","supercoolerA4","supercoolerA5","supercoolerA6","supercoolerA7","supercoolerA8","supercoolerA9","supercoolerA10","supercoolerA11",
    "supercoolerB0","supercoolerB1","supercoolerB2","supercoolerB3","supercoolerB4","supercoolerB5","supercoolerB6","supercoolerB7","supercoolerB8","supercoolerB9","supercoolerB10","supercoolerB11",
    "supercoolerC0","supercoolerC1","supercoolerC2","supercoolerC3","supercoolerC4","supercoolerC5","supercoolerC6","supercoolerC7","supercoolerC8","supercoolerC9","supercoolerC10","supercoolerC11",
    "supercoolerD0","supercoolerD1","supercoolerD2","supercoolerD3","supercoolerD4","supercoolerD5","supercoolerD6","supercoolerD7","supercoolerD8","supercoolerD9","supercoolerD10","supercoolerD11"
]
print "<<<< 2"
client_monitor_server = Thirtybirds_Client_Monitor_Server(network, hostnames)
print "<<<< 3"
client_monitor_server.daemon = True
print "<<<< 4"
client_monitor_server.start()
print "<<<< 5"

class Main(): # rules them all
    def __init__(self, network):
        self.network = network
        self.capture_path = "/home/pi/supercooler/Captures/"
        self.parsed_capture_path = "/home/pi/supercooler/ParsedCaptures/"
        self.web_interface = WebInterface()
        self.lights = Lights()
        self.door = Door(self.door_close_event_handler, self.door_open_event_handler)
        self.door.daemon = True
        self.door.start()
        self.camera_units = Camera_Units(self.network)
        self.camera_capture_delay = 3
        self.classifier = Classifier()

        # initialize inventory -- this will be recalculated on door close events
        self.inventory = []

        # map tensorflow labels to corresponding ints for web interface
        self.label_lookup = {
            "can busch"                 : 0,
            "bottle shocktop raspberry" : 1,
            "bottle ultra"              : 2,
            "bottle hoegaarden"         : 3,
            "bottle bud light"          : 4,
            "can bud light"             : 5,
            "bottle bud america"        : 6,
            "can natty"                 : 7,
            "can bud america"           : 8,
            "bottle shocktop pretzel"   : 9,
            "bottle becks"              : 10,
            "can bud ice"               : 11,
            "bottle platinum"           : 12,
            "bottle stella"             : 13,
            "bottle corona"             : 14,
            "other"                     : 15
        }

        self.web_interface.send_test_report()   



    def door_open_event_handler(self):
        print "Main.door_open_event_handler"
        self.web_interface.send_door_open()

    def door_close_event_handler(self):
        print "Main.door_close_event_handler"
        self.web_interface.send_door_close()

        # clear inventory (will be populated after classification)
        self.inventory = []

        # tell camera units to captures images at each light level
        for light_level_sequence_position in range(3):
            self.lights.play_sequence_step(light_level_sequence_position)
            self.camera_units.capture_image(light_level_sequence_position)
            time.sleep(self.camera_capture_delay)
        self.lights.all_off()

        # tell camera units to parse images and send back the data
        self.camera_units.process_images_and_report()

        # pause while conductor waits for captures, then start classification
        print "waiting for captures... see you in 90 seconds!"
        time.sleep(90)

        print "begin classification process"
        self.classify_images()

        if len(self.inventory) == 0:
            print "empty... add dummy beer"
            self.inventory[0] = {"type":1,"shelf":"A","x":10,"y":10}

        print "update web interface"
        self.web_interface.send_report(self.inventory)
        #for item in self.inventory:
        #    self.web_interface.send_report(item)

        print "done updating"


    def classify_images(self, threshold=0.6):
        # for convenience
        classifier = self.classifier
        #images = self.images
        inventory = self.inventory

        # if the best guess falls below this threshold, assume no match
        confidence_threshold = threshold

        # start tensorflow session, necessary to run classifier
        with tf.Session() as sess:
            for i, cropped_capture in enumerate(images.cropped_captures):

                print "processing_img"
                # report progress every ten images
                #if (i%10) == 0:
                #    print 'processing %dth image' % i
                #    time.sleep(1)

                # crop image and encode as jpeg (classifier expects jpeg)
                x, y, w, h = cropped_capture["bounds"]
                img_crop = images.captures[cropped_capture["img_index"]][y:y+h, x:x+w]
                img_jpg = cv2.imencode('.jpg', img_crop)[1].tobytes()

                # get a list of guesses w/ confidence in this format:
                # guesses = [(best guess, confidence), (next guess, confidence), ...]
                guesses = classifier.guess_image(sess, img_jpg)
                best_guess, confidence = guesses[0]

                # if we beat the threshold, then update the inventory accordingly
                if confidence > confidence_threshold:
                    inventory.append({
                        "type"  : self.label_lookup[best_guess],
                        "shelf" : "D",
                        "x"     : x + w/2,
                        "y"     : y + h/2,
                    })

                # TODO: move the temp sensing out of guess_image and into here


    def test_classification(self):

        # read in a test image for parsing/classification
        with open("/home/pi/supercooler/Roles/conductor/test_img.png", "rb") as f:
            img = base64.b64encode(f.read())

        # clear inventory (will be populated after classification)
        self.inventory = []

        # an example payload -- this is what the camera units send over
        payload = {
            "camera_id"     : "A02",
            "light_level"   : 2,
            "image"         : img,
            "bounds"        : [
                (0, 0, 100, 200),
                (250, 250, 200, 100),
                (0, 200, 150, 150)
            ]
        }

        images.receive_image_data(payload)  # store image data from payload
        self.classify_images(threshold=0.1)      # classify images

        print self.inventory

def network_status_handler(msg):
    print "network_status_handler", msg

def network_message_handler(msg):
    try:
        #print "network_message_handler", msg
        topic = msg[0]
        payload = eval(msg[1])
        #print "topic", topic
        if topic == "__heartbeat__":
            print "heartbeat received", msg

        # if topic == "image_capture_from_camera_unit":
        #     images.receive_and_save(payload[0],payload[1])

        if topic == "update_complete":
            print 'update complete for host: ', msg[1]

        if topic == "client_monitor_response":
           # if payload == None:
           #     return
           # client_monitor_server.add_to_queue(payload[0],payload[2],payload[1])

            print '"client_monitor_response"', msg[1] 

        if topic == "receive_image_data":
            images.receive_image_data(payload)       

    except Exception as e:
        print "exception in network_message_handler", e

def init(HOSTNAME):
    print ">>>>>>> 1"
    # setup LED control and door sensor
    #io_init()
    wpi.wiringPiSetup()
    # global network
    print ">>>>>>> 2"
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

    print ">>>>>>> 3"
    network.subscribe_to_topic("system")  # subscribe to all system messages
    network.subscribe_to_topic("found_beer")
    network.subscribe_to_topic("update_complete")
    network.subscribe_to_topic("image_capture_from_camera_unit")
    network.subscribe_to_topic("client_monitor_response")
    network.subscribe_to_topic("receive_image_data")

    print ">>>>>>> 4"
    main = Main(network)

    print ">>>>>>> 5"
    return main
