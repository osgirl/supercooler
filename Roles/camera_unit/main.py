
import base64
import commands
import cv2
import importlib
import json
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

from parser import Image_Parser

from watson_developer_cloud import VisualRecognitionV3

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
        print "Main.add_to_queue",topic, msg
        self.queue.put((topic, msg))
        print "Main.add_to_queue done"

    def capture_image_and_save(self, filename):
        print "Main.capture_image_and_save", filename
        self.camera.take_capture(filename)

    def return_env_data(self, filename):
        shelf_id = filename[:-4][:1]
        camera_id = filename[1:-6]
        light_level = filename[:-4][-1:]
        return shelf_id, camera_id, light_level

    def parse_and_crop_images(self):

        # PARSE IMAGES

        # create instance of image parser and gather captures
        print "getting ready to parse images..."
        parser = Image_Parser()
        filenames = [ filename for filename in os.listdir(self.capture_path) if filename.endswith(".png") ]

        # store references to images (will be nparrays for opencv)
        ocv_imgs = [None, None, None]

        # convert images in capture directory to nparrays, extract metadata from filename
        for filename in filenames:
            shelf_id, camera_id, light_level = self.return_env_data(filename)
            print 'loading %s' % (filename)
            ocv_imgs[int(light_level)] = cv2.imread(os.path.join(self.capture_path, filename))

        if ocv_imgs[0] is None: print 'error: no image found'; return
        print 'starting parser'

        # run parser, get image bounds and undistorted image
        bounds_list, ocv_img_with_overlay, ocv_img_out = parser.parse(ocv_imgs[0], ocv_imgs[1], ocv_imgs[2])

        # CROP IMAGES

        # iterate through list of image bounds, store cropped capture info
        cropped_image_metadata = {}
        for bounds in bounds_list:

            # crop image and encode as jpeg
            print "cropping..."
            x, y, w, h = bounds
            img_crop = ocv_img_out[y:y+h, x:x+w]
            img_jpg = cv2.imencode('.jpg', img_crop)[1].tobytes()
            print "cropped image, w,h = ", w, h

            # create filename from img data
            filename = shelf_id + camera_id + "_" + str(x) + "_" + str(y) + ".jpg"
            filepath = "/home/pi/supercooler/ParsedCaptures/" + filename
            
            cropped_image_metadata[filename] = {
                'x' :  x,
                'y' :  y,
                'w' :  w,
                'h' :  h,
            }

            # write to file
            with open(filepath, 'wb') as f:
                f.write(img_jpg)

        return cropped_image_metadata, ocv_img_with_overlay, ocv_img_out

    def send_images_to_conductor(self, raw_images, processed_image, processed_image_with_overlay ):
        # convert image to jpeg and base64-encode
        image_undistorted  = base64.b64encode(cv2.imencode('.jpg', processed_image)[1].tostring())
        image_with_overlay = base64.b64encode(cv2.imencode('.png', processed_image_with_overlay)[1].tostring())
        
        network.send("receive_image_data", to_send)
        network.send("receive_image_overlay", ("overlay_%s%s.png" % (shelf_id, camera_id),image_with_overlay))
        for i, ocv_img in enumerate(ocv_imgs):
            image_raw = base64.b64encode(cv2.imencode('.png', ocv_img)[1].tostring())
            network.send("receive_image_overlay", ("raw_%s%s_%d.png" % (shelf_id, camera_id, i),image_raw))

    def send_cropped_images_to_watson(self):
        visual_recognition = VisualRecognitionV3('2016-05-20', api_key='753a741d6f32d80e1935503b40a8a00f317e85c6')
        filepath = "/home/pi/supercooler/captures_cropped.`"
        classification_data = []
        with open( filepath, 'rb') as image_file:
            return visual_recognition.classify(images_file=image_file,  classifier_ids=['beercaps_697951100'], threshold=0.99)

    def collate_classifcation_metadata(self, classification_results, cropped_image_metadata):
        classified_image_metadata = {}
        for image in classification_results[u'images']:
            if len(image[u'classifiers']) > 0:
                classified_image_metadata[ os.path.basename(image[u'image']) ] = {
                    "score":image[u'classifiers'][0][u'classes'][0][u'score'],
                    "class":image[u'classifiers'][0][u'classes'][0][u'class'],
                }
        print classified_image_metadata
        for key,val in classified_image_metadata.items():
            classified_image_metadata[key]['x'] = cropped_image_metadata[key]['x']
            classified_image_metadata[key]['y'] = cropped_image_metadata[key]['y']
            classified_image_metadata[key]['w'] = cropped_image_metadata[key]['w']
            classified_image_metadata[key]['h'] = cropped_image_metadata[key]['h']
        return classified_image_metadata

    def process_images_and_report(self):
        # parse and crop Captures 
        cropped_image_metadata, processed_image_with_overlay, processed_image = self.parse_and_crop_images()
        # send_images_to_conductor(None, processed_image, processed_image_with_overlay)

        # prepare images to send to Watson
        filename_zipped = "/home/pi/supercooler/captures_cropped.zip"
        subprocess.call(['zip', '-j', filename_zipped, '/home/pi/supercooler/ParsedCaptures/*' ])

        # send to Watson for classification
        classification_results = self.send_cropped_images_to_watson()
        collated_metadata = self.collate_classifcation_metadata(classification_results, cropped_image_metadata)
        print collated_metadata

    def return_raw_images(self):
        if "coolerB" in self.hostname:
            filenames = [ filename for filename in os.listdir(self.capture_path) if filename.endswith(".png") ]
            ocv_imgs  = [None, None, None]

            for filename in filenames:
                shelf_id, camera_id, light_level = self.return_env_data(filename)
                print 'loading %s' % (filename)
                ocv_imgs[int(light_level)] = cv2.imread(os.path.join(self.capture_path, filename))

            print "sending raw images"
            for i, ocv_img in enumerate(ocv_imgs):

                image_raw = base64.b64encode(cv2.imencode('.png', ocv_img)[1].tostring())
                network.send("receive_image_overlay", ("raw_%s%s_%d.png" % (shelf_id, camera_id, i),image_raw))

            print "sent raw images okay"

    def run(self):
        while True:
            print "Main.run 1"
            topic, msg = self.queue.get(True)
            print "Main.run 2"
            if topic == "capture_image":
                if msg in [0, "0"]: # on request 0, empty directory
                    previous_filenames = [ previous_filename for previous_filename in os.listdir(self.capture_path) if previous_filename.endswith(".png") ]
                    for previous_filename in previous_filenames:
                        os.remove(   "{}{}".format(self.capture_path,  previous_filename) )
                filename = "{}_{}.png".format(self.hostname[11:], msg) 
                self.capture_image_and_save(filename)
            if topic == "process_images_and_report":
                self.process_images_and_report()
            if topic == "return_raw_images":
                self.return_raw_images()


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
    elif topic == hostname:
        print "testing png file sending"

        filename = "capture" + hostname[11:] + ".png"
        main.camera.take_capture(filename)

        with open("/home/pi/supercooler/Captures/" + filename, "rb") as f:
            data = f.read()
            network.send("found_beer", base64.b64encode(data))
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
    network.subscribe_to_topic("return_raw_images")

    return main

    
