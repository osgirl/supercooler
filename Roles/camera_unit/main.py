
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


    # ---> CAMERA
    def capture_image_and_save(self, filename):
        print "Main.capture_image_and_save", filename
        self.camera.take_capture(filename)
        time.sleep(0.5)
        self.copy_to_gdrive(filename)

    # ---->  NETWORK
    def copy_to_gdrive(self,filename):
        print "copy_to_gdrive:", commands.getstatusoutput("gdrive upload {}".format(os.path.join(self.capture_path, filename)))[1]
        
    # ---> UTILS
    def return_env_data(self, filename):
        shelf_id = filename[:-4][:1]
        camera_id = filename[1:-6]
        light_level = filename[:-8][-1:]
        return shelf_id, camera_id, light_level

    def send_images_to_conductor(self, raw_images, processed_image, processed_image_with_overlay ):
        # convert image to jpeg and base64-encode
        image_undistorted  = base64.b64encode(cv2.imencode('.jpg', processed_image)[1].tostring())
        image_with_overlay = base64.b64encode(cv2.imencode('.png', processed_image_with_overlay)[1].tostring())
        network.send("receive_image_data", to_send)
        network.send("receive_image_overlay", ("overlay_%s%s.png" % (shelf_id, camera_id),image_with_overlay))
        for i, ocv_img in enumerate(ocv_imgs):
            image_raw = base64.b64encode(cv2.imencode('.png', ocv_img)[1].tostring())
            network.send("receive_image_overlay", ("raw_%s%s_%d.png" % (shelf_id, camera_id, i),image_raw))


    # ---> OBJECT DETECTION
    def parse_and_crop_images(self):
        previous_filenames = [ previous_filename for previous_filename in os.listdir("/home/pi/supercooler/ParsedCaptures/") if previous_filename.endswith(".jpg") ]
        print "delete previous cropped images", previous_filenames
        for previous_filename in previous_filenames:
            os.remove(   "{}{}".format("/home/pi/supercooler/ParsedCaptures/",  previous_filename) )
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
        if ocv_imgs[0] is None: 
                print 'error: no image found'
                return False, None, None, None
        print 'starting parser'
        # run parser, get image bounds and undistorted image
        bounds_list, ocv_img_with_overlay, ocv_img_out = parser.parse(ocv_imgs[0], ocv_imgs[1], ocv_imgs[2])
        # CROP IMAGES
        # iterate through list of image bounds, store cropped capture info
        cropped_image_metadata = {}
        for bounds in bounds_list:
            try:
                # crop image and encode as jpeg
                print "cropping..."
                x, y, w, h = bounds
                print "bounds >>>>>", x, y, w, h
                img_crop = ocv_img_out[y:y+h, x:x+w]
                print "img_crop >>>>>", repr(img_crop)
                #img_jpg = cv2.imencode('.jpg', img_crop)[1].tobytes()
                print "cropped image, w,h = ", w, h
                # create filename from img data
                filename = shelf_id + camera_id + "_" + str(x) + "_" + str(y) + ".jpg"
                filepath = "/home/pi/supercooler/ParsedCaptures/" + filename
                print "filepath=", filepath
                cropped_image_metadata[filename] = {
                    'x' :  x,
                    'y' :  y,
                    'w' :  w,
                    'h' :  h,
                }
                print "cropped_image_metadata=", cropped_image_metadata
                # write to file
                #with open(filepath, 'wb') as f:
                #    f.write(img_jpg)
                cv2.imwrite(filepath, img_crop)
            except Exception as e:
                print "exception in parse_and_crop_images", e

        return True, cropped_image_metadata, ocv_img_with_overlay, ocv_img_out


    def send_cropped_images_to_watson(self):
        # TODO: delete this API key from Bluemix after the demo
        visual_recognition = VisualRecognitionV3('2016-05-20', api_key='4fd7cd5854ae7a1c63f1835ddd63a2a7779a73d0')
        filepath = "/home/pi/supercooler/captures_cropped.zip"
        time.sleep(random.randrange(0,15))
        # send to watson
        with open(filepath, 'rb') as image_file:
            res = visual_recognition.classify(images_file=image_file, classifier_ids=['supercooler3_1124392282'])
        return res
        # with open( filepath, 'rb') as image_file:
        #     return visual_recognition.classify(images_file=image_file,  classifier_ids=['beercaps_697951100'], threshold=0.99)

    def collate_classifcation_metadata(self, classification_results, cropped_image_metadata):
        print "collate_classifcation_metadata"
        classified_image_metadata = {}
        for image in classification_results[u'images']:
            if image.has_key(u'classifiers'):
                if len(image[u'classifiers']) > 0:
                    # stella won't be in the fridge for the demo, so remove that as a possibility
                    # 'candidates' is a list of dicts in the form {'class':str, 'score':float} 
                    candidates = [d for d in image[u'classifiers'][0][u'classes'] if not (d[u'class'] == 'bottlestella')]
                    if len(candidates) == 0: continue
                    candidates = [d for d in candidates if not (d[u'class'] == 'bottleplatinum')]
                    if len(candidates) == 0: continue
                    candidates = [d for d in candidates if not (d[u'class'] == 'bottlebecks')]
                    if len(candidates) == 0: continue
                    candidates = [d for d in candidates if not (d[u'class'] == 'bottleultra')]  
                    if len(candidates) == 0: continue
                    candidates = [d for d in candidates if not (d[u'class'] == 'bottlehoegaarden')]
                    if len(candidates) == 0: continue
                    candidates = [d for d in candidates if not (d[u'class'] == 'bottleshocktoppretzel')]
                    if len(candidates) == 0: continue
                    candidates = [d for d in candidates if not (d[u'class'] == 'bottleshcoktopraspberry')]
                    if len(candidates) == 0: continue
                    candidates = [d for d in candidates if not (d[u'class'] == 'bottlecorona')]
                    if len(candidates) == 0: continue
                    candidates = [d for d in candidates if not (d[u'class'] == 'cannaturallight')]
                    if len(candidates) == 0: continue
                    candidates = [d for d in candidates if not (d[u'class'] == 'canbudlight')]
                    if len(candidates) == 0: continue
                    # skip to next image if there's no remaining candidates
                    if len(candidates) == 0: continue
                    # highest_confidence_classification = sorted(image[u'classifiers'][0][u'classes'], key=itemgetter('score'))[-1]
                    highest_confidence_classification = sorted(candidates, key=itemgetter('score'))[-1]                    
                    #if highest_confidence_classification[u'score'] >0.95:
                    # print "collate_classifcation_metadata 1", image
                    classified_image_metadata[ os.path.basename(image[u'image']) ] = {
                        "score":highest_confidence_classification[u'score'],
                        "class":highest_confidence_classification[u'class'],
                    }
        print classified_image_metadata
        print ""
        print cropped_image_metadata
        for key,val in classified_image_metadata.items():
            classified_image_metadata[key]['x'] = cropped_image_metadata[str(key)]['x']
            classified_image_metadata[key]['y'] = cropped_image_metadata[str(key)]['y']
            classified_image_metadata[key]['w'] = cropped_image_metadata[str(key)]['w']
            classified_image_metadata[key]['h'] = cropped_image_metadata[str(key)]['h']
        return classified_image_metadata

    def process_images_and_report(self):
        # parse and crop Captures 
        status, cropped_image_metadata, processed_image_with_overlay, processed_image = self.parse_and_crop_images()
        if not status:
            print "Exception in parse_and_crop_images.  Probably camera trouble"
            return
        # send_images_to_conductor(None, processed_image, processed_image_with_overlay)
        print cropped_image_metadata, processed_image_with_overlay, processed_image
        shelf = self.hostname[11:][:1]
        camera = self.hostname[12:]
        #catch case of empty directory
        if len(cropped_image_metadata.keys()):
            time.sleep(5)
            # prepare images to send to Watson
            filename_zipped = "/home/pi/supercooler/captures_cropped.zip"
            commands.getstatusoutput("rm /home/pi/supercooler/captures_cropped.zip")
            time.sleep(2)
            commands.getstatusoutput("cd /home/pi/supercooler/; zip -j captures_cropped.zip ParsedCaptures/*.jpg")
            #subprocess.call(['zip', '-j', filename_zipped, '/home/pi/supercooler/ParsedCaptures/*' ])
            # send to Watson for classification
            classification_results = self.send_cropped_images_to_watson()
            print "++++++++++++++++++"
            print "classification_results", classification_results
            print "++++++++++++++++++"
            collated_metadata = self.collate_classifcation_metadata(classification_results, cropped_image_metadata)
        else:
            collated_metadata = {}
        print collated_metadata
        self.network.send("classification_data_to_conductor", (shelf, camera, collated_metadata))

    def return_raw_images(self):
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

    def  create_file_name(self, timestamp, light_level, raw_or_processed):
        shelf = self.hostname[11:][:1]
        camera = self.hostname[12:]
        return "{}_{}_{}_{}_{}.png".format(timestamp, shelf,  camera, light_level, raw_or_processed) 

    def run(self):
        while True:
            # print "Main.run 1"
            topic, msg = self.queue.get(True)
            # print "Main.run 2"
            if topic == "capture_image":
                print ">>>>>>>>>>>>>>", repr(msg)
                light_level, timestamp = eval(msg)
                if light_level in [0, "0"]: # on request 0, empty directory
                    previous_filenames = [ previous_filename for previous_filename in os.listdir(self.capture_path) if previous_filename.endswith(".png") ]
                    for previous_filename in previous_filenames:
                        os.remove(   "{}{}".format(self.capture_path,  previous_filename) )
                self.capture_image_and_save( self.create_file_name(timestamp, light_level, "raw") )
            if topic == "process_images_and_report":
                self.process_images_and_report()
            if topic == "return_raw_images":
                self.return_raw_images()


# TODO: this function is used for generating training data and contains some
# duplicate functionality -- maybe get rid of later?
def capture_and_upload_image(timestamp, light, gdir, clear_dir):
    print "capture and upload image"

    if clear_dir:
        # first, remove all existing files from the captures directory
        old_filenames = os.listdir('/home/pi/supercooler/Captures')
        for filename in old_filenames:
            os.remove('/home/pi/supercooler/Captures/' + filename)

    # create filename from time, light, and location
    id_str = main.hostname[11] + main.hostname[12:].zfill(2)
    filename = id_str + "_" + str(light) + "_" + timestamp + ".png"

    # take picture and save image to file
    self.camera.take_capture(filename)
    time.sleep(0.5)

    # upload image to specified directory in google drive
    filepath = '/home/pi/supercooler/Captures/' + filename
    subprocess.call(['gdrive', 'upload', '-p', gdir, filepath])

# TODO: this function is used for generating training data and contains some
# duplicate functionality -- maybe get rid of later?
def parse_and_annotate_images(timestamp, gdir_annotated, gdir_parsed):
    print "parse and annotate images"

    # ------- PARSE IMAGES ----------------------------------------------------

    # set up image parser and get list of recent captures
    parser = Image_Parser()
    capture_path = '/home/pi/supercooler/Captures'
    filenames = [ filename for filename in os.listdir(capture_path) \
        if filename.endswith(".png") ]
    
    # store references to images (will be nparrays for opencv)
    ocv_imgs = [None, None, None]
    
    # convert images in capture directory to nparrays
    for filename in filenames:
        ocv_imgs[int(filename[4])] = \
            cv2.imread(os.path.join(self.capture_path, filename))

    # run parser, get image bounds and undistorted image
    bounds_list, ocv_img_with_overlay, ocv_img_out = \
        parser.parse(ocv_imgs[0], ocv_imgs[1], ocv_imgs[2])

    # empty ParsedCaptures directory
    old_filenames = os.listdir('/home/pi/supercooler/ParsedCaptures')
    for filename in old_filenames:
        os.remove('/home/pi/supercooler/Captures/' + filename)


    # ------- SAVE ANNOTATION -------------------------------------------------

    # prep for writing to file (construct filename + filepath)
    id_str = main.hostname[11] + main.hostname[12:].zfill(2)
    filename = id_str + "_annotated_" + timestamp + ".jpg"
    filepath = "/home/pi/supercooler/ParsedCaptures/" + filename
    
    # encode as jpeg and write to file
    overlay_jpg = cv2.imencode('.jpg', ocv_img_with_overlay)[1].tobytes()
    with open(filepath, 'wb') as f:
        f.write(overlay_jpg)
    
    # upload to google drive
    subprocess.call(['gdrive', 'upload', '-p', gdir_annotated, filepath])

    
    # -------- CROP & UPLOAD IMAGES -------------------------------------------

    # make a new directory for parsed images
    mkdir_stdout = \
        subprocess.check_output(['gdrive', 'mkdir', '-p', gdir_parsed, id_str])
    gdir_cam = mkdir_stdout.split(" ")[1]

    for bounds in bounds_list:
        # crop image and encode as jpeg
        x, y, w, h = bounds
        img_crop = ocv_img_out[y:y+h, x:x+w]
        img_jpg = cv2.imencode('.jpg', img_crop)[1].tobytes()
            
        # create filename from img data
        filename = id_str + "_" + timestamp + "_" + str(x) + "_" + str(y) + ".jpg"
        filepath = "/home/pi/supercooler/ParsedCaptures/" + filename
            
        # write cropped image to file and upload to drive
        with open(filepath, 'wb') as f:
            f.write(img_jpg)
        subprocess.call(['gdrive', 'upload', '-p', gdir_cam, filepath])


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
        print "starting remote_update"
        [cool, birds, update, upgrade] = eval(msg[1])
        print repr([cool, birds, update, upgrade])
        if cool:
            print "cool"
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/supercooler')
        if birds:
            print "birds"
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/thirtybirds_2_0')
        network.send("update_complete", network_info.getHostName())

    # take a picture and upload the image to google drive
    elif topic == "capture_and_upload":
        capture_and_upload_image(*eval(data))

    elif topic == "parse_and_annotate":
        parse_and_annotate_images(*eval(data))

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
    main = Main(HOSTNAME, network)
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
    network.subscribe_to_topic("capture_and_upload")
    network.subscribe_to_topic("parse_and_annotate")

    return main

    
