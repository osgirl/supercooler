
import base64
import commands
import importlib
import json
import os
import settings 
import sys
import threading
import time
import subprocess
import Queue

from thirtybirds_2_0.Network.manager import init as network_init
from thirtybirds_2_0.Network.email_simple import init as email_init
from thirtybirds_2_0.Adaptors.Cameras.elp import init as camera_init
from thirtybirds_2_0.Updates.manager import init as updates_init
from thirtybirds_2_0.Network.info import init as network_info_init
network_info = network_info_init()

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
DEVICES_PATH = "%s/Hosts/" % (BASE_PATH )
THIRTYBIRDS_PATH = "%s/thirtybirds" % (UPPER_PATH )

import image_detection_bottles_and_cans
import image_parser

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)

class Thirtybirds_Client_Monitor_Client():
    def __init__(self, hostname, network ):
        self.network = network
        self.hostname = hostname

    def get_pickle_version(self):
        (updates, ghStatus, bsStatus) = updates_init("/home/pi/supercooler", False, False)
        return updates.read_version_pickle()

    def get_git_timestamp(self):
        return commands.getstatusoutput("cd /home/pi/supercooler/; git log -1 --format=%cd")[1]   

    def send_client_status(self):
        pickle_version = self.get_pickle_version()
        git_timestamp = self.get_git_timestamp()
        self.network.send("client_monitor_response", (self.hostname,pickle_version, git_timestamp))

class Main(threading.Thread):
    def __init__(self, hostname, network):
        threading.Thread.__init__(self)
        self.hostname = hostname
        self.network = network
        self.capture_path = "/home/pi/supercooler/Captures/"
        self.parsed_capture_path = "/home/pi/supercooler/ParsedCaptures/"
        self.camera = camera_init(self.capture_path)
        self.queue = Queue.Queue()
        self.max_capture_age_to_use = 120  # seconds
        self.thirtybirds_client_monitor_client = Thirtybirds_Client_Monitor_Client(hostname, network)

    def add_to_queue(self, topic, msg):
        self.queue.put((topic, msg))

    def capture_image_and_save(self, filename):
        self.camera.take_capture(filename)

    def process_images_and_report(self):
        # send images back to server
        filenames = [ filename for filename in os.listdir(self.capture_path) if filename.endswith(".png") ]
        for filename in filenames:
            with open("{}{}".format(self.capture_path, filename), "rb") as image_file:
                image_data = [
                    filename, 
                    base64.b64encode(image_file.read())
                ]
                network.send("image_capture_from_camera_unit", image_data)

        # clear previous parsed capture files
        previous_parsed_capture_filenames = [ previous_parsed_capture_filename for previous_parsed_capture_filename in os.listdir(self.parsed_capture_path) if previous_parsed_capture_filename.endswith(".png") ]
        for previous_parsed_capture_filename in previous_parsed_capture_filenames:
            os.remove(previous_parsed_capture_filename)

        # loop through images
        for filename in filenames:
            bounds = image_detection_bottles_and_cans.detect_bounds( filename, min_size )
            print filename, bounds

            #image_metadata = map(__some_process__, bounds)
            #for image in image_metadata:
            #    filename = ""
            #    image_parser.parse( filename )
        # copy directory to conductor
        # copy metadata to conductor


    def run(self):
        while True:
            topic, msg = self.queue.get(True)
            if topic == "capture_image":
                if msg in [0, "0"]: # on request 0, empty directory
                    previous_filenames = [ previous_filename for previous_filename in os.listdir(self.capture_path) if previous_filename.endswith(".png") ]
                    for previous_filename in previous_filenames:
                        os.remove(previous_filename)
                    filename = "{}_{}.png".format(self.hostname[11:], msg) 
                    self.capture_image_and_save(filename)
            if topic == "process_images_and_report":
                self.process_images_and_report()


def network_status_handler(msg):
    print "network_status_handler", msg

def network_message_handler(msg):

    print "network_message_handler", msg
    topic = msg[0]
    data = msg[1]
    #host, sensor, data = yaml.safe_load(msg[1])
    if topic == "__heartbeat__":
        print "heartbeat received", msg

    elif topic == "reboot":
        os.system("sudo reboot now")

    elif topic == "remote_update":
        print "satarting remote_update"
        [cool, birds, update, upgrade] = eval(msg[1])
        print repr([cool, birds, update, upgrade])
        if cool:
            print "cool"
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/supercooler')
        if birds:
            print "birds"
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/thirtybirds_2_0')
        network.send("update_complete", network_info.getHostName())

    elif topic == "remote_update_scripts":
        updates_init("/home/pi/supercooler", False, True)
        network.send("update_complete", network_info.getHostName())

    elif topic == "client_monitor_request":
        network.send("client_monitor_response", main.thirtybirds_client_monitor_client.send_client_status())
        
    else: # [ "capture_image" ]
        main.add_to_queue(topic, data)
        
    """    
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
    """


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
    network.subscribe_to_topic("capture_image")
    network.subscribe_to_topic("remote_update")
    network.subscribe_to_topic(HOSTNAME)
    network.subscribe_to_topic("client_monitor_request")

    
