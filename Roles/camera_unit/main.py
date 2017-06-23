
import base64
import commands
import cv2
import importlib
import json
import numpy as np
import os
import Queue
import settings 
import sys
import subprocess
import threading
import time

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

class Image_Parser():
    def __init__(self, hostname, network, min_size=65):
        self.hostname = hostname
        self.network = network
        self.min_size = min_size
        self.distortion = np.array([[-6.0e-5, 0.0, 0.0, 0.0]], np.float64)
        self.max_confdence = 1.0
    
    def mask_beers(self, img):
        # create masks to accumulate blobs detected by each pass
        mask_distorted = np.zeros(img.shape[:2], dtype = 'uint8')
        mask = np.zeros(img.shape[:2], dtype = 'uint8')
        
        # distorted:

        # CLAHE and Otsu threshold
        equalized = equalize_histogram(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        mask_distorted += mask_blobs(equalized)

        # adaptive threshold
        processed = process_split(img)
        mask_distorted += mask_blobs(processed)

        # undistorted:

        img_out = cv2.undistort(img, self.cam, self.distortion )

        # CLAHE and Otsu threshold
        equalized = equalize_histogram(cv2.cvtColor(img_out, cv2.COLOR_BGR2GRAY))
        mask += mask_blobs(equalized)

        # adaptive threshold
        processed = process_split(img_out)
        mask += mask_blobs  (processed)
        
        # undistort results from distorted image; sum with undistorted results
        mask += cv2.undistort(mask_distorted, self.cam, self.distortion )

        return mask

    def find_beers(self, mask, vis):
        _, contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            if max(w, h) < self.min_size: continue

            (cx,cy), radius = cv2.minEnclosingCircle(contour)
            center = (int(cx),int(cy))
            radius = int(radius)

            circlePoints = cv2.ellipse2Poly(center, (radius,radius), 0, 0, 360, 1)
            confidence = cv2.matchShapes(contour, circlePoints, 1, 0.0)

            if confidence > self.max_confdence: continue
                
            result.append((x, y, w, h))

            if self.interactive | self.save_visuals:
                cv2.polylines(vis, [contour], 0, (0,0,255), 1)
                cv2.rectangle(vis, (x,y), (x+w,y+h), (0,255,0), 2)
                cv2.circle(vis, center, radius, (0,255,0), 2)                      
                cv2.putText(vis, '%.3f' % confidence, center, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,255), 2)
        
        if self.interactive: plt.imshow(vis), plt.show()
        return (result, vis)

    def parse(self, filename, filename_50=None, filename_0=None):
        img = cv2.imread(filename)
        img_weighted = img.copy()
        self.cam = calc_camera_matrix(img.shape[:2])
        mask_final = self.mask_beers(img)
        img_out = cv2.undistort(img, self.cam, self.distortion )
        beer_bounds, vis = self.find_beers(mask_final, img_out.copy())
        return beer_bounds, vis, img_out

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
        print "process_images_and_report 1"
        filenames = [ filename for filename in os.listdir(self.capture_path) if filename.endswith(".png") ]
        print "process_images_and_report 2", filenames
        for filename in filenames:
            print "process_images_and_report 3", filename
            with open("{}{}".format(self.capture_path, filename), "rb") as image_file:
                image_data = [
                    filename, 
                    base64.b64encode(image_file.read())
                ]
                network.send_blob("image_capture_from_camera_unit", image_data)
        print "process_images_and_report 4"
        # clear previous parsed capture files
        previous_parsed_capture_filenames = [ previous_parsed_capture_filename for previous_parsed_capture_filename in os.listdir(self.parsed_capture_path) if previous_parsed_capture_filename.endswith(".png") ]
        print "process_images_and_report 5", previous_parsed_capture_filenames
        for previous_parsed_capture_filename in previous_parsed_capture_filenames:
            print "process_images_and_report 6", previous_parsed_capture_filename
            os.remove(previous_parsed_capture_filename)

        # loop through images
        for filename in filenames:
            print "process_images_and_report 7", filename
            parser = Image_Parser()

            bounds, vis, img_out = parser.parse(camera, os.path.join(self.capture_path, filename))
            print "bounds: ", bounds 
            #print filename, bounds, vis, img_out
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
                        os.remove(   "{}{}".format(self.capture_path,  previous_filename) )
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

    
