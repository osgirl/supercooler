
import base64
import commands
import cv2
import importlib
import os
import settings 
import sys
import subprocess
import time

from thirtybirds_2_0.Network.manager import init as network_init
from thirtybirds_2_0.Adaptors.Cameras.elp import init as camera_init
from thirtybirds_2_0.Updates.manager import init as updates_init
from thirtybirds_2_0.Network.info import init as network_info_init

from parser import Image_Parser

network_info = network_info_init()

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
DEVICES_PATH = "%s/Hosts/" % (BASE_PATH )
THIRTYBIRDS_PATH = "%s/thirtybirds" % (UPPER_PATH )

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)

capture_path = "/home/pi/supercooler/Captures/"
camera = camera_init(capture_path)
network = None

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


# captures an image and uploads to google drive. if clear_dir == True,
# empties the Captures directory
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
    main.camera.take_capture(filename)
    time.sleep(0.5)

    # upload image to specified directory in google drive
    filepath = '/home/pi/supercooler/Captures/' + filename
    subprocess.call(['gdrive', 'upload', '-p', gdir, filepath])


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
            cv2.imread(os.path.join(capture_path, filename))

    # run parser, get image bounds and undistorted image
    bounds_list, ocv_img_with_overlay, ocv_img_out = \
        parser.parse(ocv_imgs[0], ocv_imgs[1], ocv_imgs[2])

    # empty ParsedCaptures directory
    for filename in os.listdir('/home/pi/supercooler/ParsedCaptures'):
        if filename.endswith(".jpg"):
            os.remove('/home/pi/supercooler/ParsedCaptures/' + filename)


    # ------- SAVE ANNOTATION -------------------------------------------------

    # prep for writing to file (construct filename + filepath)
    id_str = main.hostname[11] + main.hostname[12:].zfill(2)
    filename = id_str + "_annotated_" + timestamp + ".jpg"
    filepath = "/home/pi/supercooler/ParsedCaptures/" + filename
    
    # encode as jpeg and write to file
    overlay_jpg = cv2.imencode('.jpg', ocv_img_with_overlay)[1].tostring()
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
        img_jpg = cv2.imencode('.jpg', img_crop)[1].tostring()
            
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

    if topic == "__heartbeat__":
        print "heartbeat received", msg

    elif topic == "reboot":
        os.system("sudo reboot now")

    elif topic == "remote_update":
        print "starting remote_update"
        [cool, birds, update, upgrade] = eval(msg[1])
        if cool:
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/supercooler')
        if birds:
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/thirtybirds_2_0')
        network.send("update_complete", network_info.getHostName())

    # take a picture and upload the image to google drive
    elif topic == "capture_and_upload":
        capture_and_upload_image(*eval(data))

    elif topic == "parse_and_annotate":
        print 'parse_and_annotate'
        parse_and_annotate_images(*eval(data))

    elif topic == "remote_update_scripts":
        updates_init("/home/pi/supercooler", False, True)
        network.send("update_complete", network_info.getHostName())

    # response to client monitor topics
    elif topic == "client_monitor_request":
        network.send("client_monitor_response", main.thirtybirds_client_monitor_client.send_client_status())
        
def init(hostname):
    global network
    network = network_init(
        hostname=hostname,
        role="client",
        discovery_multicastGroup=settings.discovery_multicastGroup,
        discovery_multicastPort=settings.discovery_multicastPort,
        discovery_responsePort=settings.discovery_responsePort,
        pubsub_pubPort=settings.pubsub_pubPort,
        message_callback=network_message_handler,
        status_callback=network_status_handler
    )

    thirtybirds_client_monitor_client = Thirtybirds_Client_Monitor_Client(hostname, network)

    network.subscribe_to_topic("system")  # subscribe to all system messages
    network.subscribe_to_topic("reboot")
    network.subscribe_to_topic("remote_update")
    network.subscribe_to_topic(hostname)
    network.subscribe_to_topic("client_monitor_request")
    network.subscribe_to_topic("capture_and_upload")
    network.subscribe_to_topic("parse_and_annotate")

    return None

    
