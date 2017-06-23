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

import numpy as np

class Door(threading.Thread):
    def __init__(self, door_close_event_callback, door_open_event_callback):
        threading.Thread.__init__(self)
        self.closed = True
        self.door_pin_number = 29
        self.last_closure = time.time()
        self.estmated_inventory_duration = 60
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
                    self.door_close_event_callback(True if self.last_closure + self.estmated_inventory_duration <= time.time() else False)
                else: 
                    self.door_open_event_callback()
            time.sleep(0.5)

class Lights():
    def __init__(self):
        self.pwm_pins = [21, 22, 23, 24]
        self.light_sequence_levels = [ 100, 50, 0]
        for pwm_pin in self.pwm_pins:
            wpi.pinMode(pwm_pin, wpi.OUTPUT)
            wpi.softPwmCreate(pwm_pin, 0, 100)

    def set_level_shelf(self, id, value):
        wpi.softPwmWrite(self.pwm_pins[id], value)

    def set_level_all(self, value):
        for shelf_id in range(4):
            self.set_level_shelf(shelf_id, value)

    def play_sequence_step(self, step):
        self.set_level_all(self.light_sequence_levels[step])

    def play_test_sequence(self):
        for j in xrange(-100, 101):
            for i in xrange(4): self.set_level_shelf(i, 100 - abs(j))
            wpi.delay(10)

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
        self.captures = {}
        self.cropped_captures = {}

    # def receive_and_save(self, filename, raw_data):
    #     file_path = "{}{}".format(self.capture_path,filename)
    #     print "receive_and_save", file_path
    #     image_64_decode = base64.decodestring(raw_data) 
    #     image_result = open(file_path, 'wb') # create a writable image and write the decoding result
    #     image_result.write(image_64_decode)
    # def clear_captures(self):
    #     previous_filenames = [ previous_filename for previous_filename in os.listdir(self.capture_path) if previous_filename.endswith(".png") ]
    #     for previous_filename in previous_filenames:
    #         os.remove(   "{}{}".format(self.capture_path,  previous_filename) )

    def receive_image_data(self, payload):

        # decode and store image as numpy array
        img_arr = np.fromstring(base64.decodestring(payload["image"]), np.uint8)
        img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
        self.captures.append(img)
        index = self.captures.length - 1    # store reference to index for crops

        # iterate through list of image bounds, store cropped capture info
        for i, bounds in payload["bounds"]:
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
    def __init__(self, network, update_period=120):
        threading.Thread.__init__(self)
        self.update_period = update_period
        self.current_clients = {}
        self.remembered_clients = {}
        self.network = network
        self.queue = Queue.Queue()
        
    def add_to_queue(self, hostname, git_pull_date, pickle_version):
        self.queue.put((hostname, git_pull_date, pickle_version, time.time()))

    def print_remembered_clients(self):
        print ""
        print "REMEMBERED CLIENTS:"
        for hostname in sorted(self.remembered_clients.iterkeys()):
            print "%s: %s : %s: %s" % (hostname, self.remembered_clients[hostname]["timestamp"], self.remembered_clients[hostname]["pickle_version"], self.remembered_clients[hostname]["git_pull_date"])

    def print_current_clients(self):
        print ""
        print "CURRENT CLIENTS:"
        for hostname in sorted(self.current_clients.iterkeys()):
            print "%s: %s : %s: %s" % (hostname, self.current_clients[hostname]["timestamp"], self.current_clients[hostname]["pickle_version"], self.current_clients[hostname]["git_pull_date"])

    def run(self):
        while True:
            self.network.send("client_monitor_request", "")
            time.sleep(self.update_period)
            self.current_clients = {}
            while not self.queue.empty():
                [hostname, git_pull_date, pickle_version, timestamp] = self.queue.get()
                #print ">>", hostname, git_pull_date, pickle_version, timestamp
                client_data = {
                    "git_pull_date":git_pull_date,
                    "pickle_version":pickle_version,
                    "timestamp":timestamp,
                }
                self.remembered_clients[hostname]  = dict(client_data)
                self.current_clients[hostname]  = dict(client_data)
            self.print_remembered_clients()
            self.print_current_clients()


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
        self.client_monitor_server = Thirtybirds_Client_Monitor_Server(network)
        self.client_monitor_server.daemon = True
    	self.client_monitor_server.start()

        # initialize inventory -- this will be recalculated on door close events
        self.inventory = {
            "can busch"                 : 0,
            "bottle shocktop raspberry" : 0,   
            "bottle ultra"              : 0,
            "bottle hoegaarden"         : 0,
            "bottle bud light"          : 0,
            "can bud light"             : 0,
            "bottle bud america"        : 0,
            "can natty"                 : 0,
            "can bud america"           : 0,
            "bottle shocktop pretzel"   : 0,
            "bottle becks"              : 0,
            "other"                     : 0,
            "can bud ice"               : 0,
            "bottle platinum"           : 0,
            "bottle stella"             : 0,
            "bottle corona"             : 0
        }

    def door_open_event_handler(self):
        print "Main.door_open_event_handler"
        self.web_interface.send_door_open()

    def door_close_event_handler(self, start_inventory):
        print "Main.door_close_event_handler , start_inventory= ", start_inventory
        self.web_interface.send_door_close()
        if not start_inventory: 
            return

        # clear inventory (will be populated after classification)
        for i in self.inventory: self.inventory[i] = 0

        for light_level_sequence_position in range(3):
            self.lights.play_sequence_step(light_level_sequence_position)
            self.camera_units.capture_image(light_level_sequence_position)
            time.sleep(self.camera_capture_delay)
        self.lights.all_off()
        self.camera_units.process_images_and_report()

        # pause while conductor waits for captures, then start classification
        time.sleep(90)
        self.classify_images()

    def classify_images(self, threshold=0.6):
        # for convenience
        classifier = self.classifier
        images = self.images
        inventory = self.inventory

        # if the best guess falls below this threshold, assume no match
        confidence_threshold = threshold

        # start tensorflow session, necessary to run classifier
        with tf.Session() as sess:
            for i, cropped_capture in enumerate(images.cropped_captures):

                # report progress every ten images
                if (i%10) == 0:
                    print 'processing %dth image' % i
                    time.sleep(1)

                # crop image and encode as jpeg (classifier expects jpeg)
                x, y, w, h = cropped_capture.bounds
                img_crop = images.captures[cropped_capture.img_index][y:y+h, x:x+w]
                img_jpg = cv2.imencode('.jpg', img_crp).tobytes()

                # get a list of guesses w/ confidence in this format:
                # guesses = [(best guess, confidence), (next guess, confidence), ...]
                guesses = classifier.guess_image(sess, img_jpg)
                best_guess, confidence = guesses[0]

                # if we beat the threshold, then update the inventory accordingly
                if confidence > confidence_threshold:
                    inventory[best_guess] += 1

                # TODO: move the temp sensing out of guess_image and into here


    def test_classification():

        # read in a test image for parsing/classification
        with open("/home/pi/supercooler/Roles/conductor/test_img.png", "rb") as f:
            img = base64.b64encode(f.read())

        # clear inventory (will be populated after classification)
        for i in self.inventory: self.inventory[i] = 0

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

        # clear inventory (will be populated after classification)
        for i in self.inventory: self.inventory[i] = 0

        images.receive_image_data(payload)  # store image data from payload
        classify_images(threshold=0.1)      # classify images

        print self.inventory

def network_status_handler(msg):
    pass
    #print "network_status_handler", msg

def network_message_handler(msg):
    try:
        #print "network_message_handler", msg
        topic = msg[0]
        payload = eval(msg[1])
        #print "topic", topic
        if topic == "__heartbeat__":
            print "heartbeat received", msg
        if topic == "image_capture_from_camera_unit":
            images.receive_and_save(payload[0],payload[1])

        if topic == "update_complete":
            print 'update complete for host: ', msg[1]

        if topic == "client_monitor_response":
            print '"client_monitor_response"', msg[1] 

        if topic == "receive_parsed_image_data":
            images.receive_parsed_image_data(payload)       

    except Exception as e:
        print "exception in network_message_handler", e

def init(HOSTNAME):
    # setup LED control and door sensor
    #io_init()
    wpi.wiringPiSetup()
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

    main = Main(network)
