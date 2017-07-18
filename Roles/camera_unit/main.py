
import base64
import commands
import cv2
import importlib
import json
import math
import numpy as np
from operator import itemgetter
import os
import Queue
import random
import settings 
import sys
import subprocess
import threading
import time
import traceback

from thirtybirds_2_0.Network.manager import init as thirtybirds_network
from thirtybirds_2_0.Network.email_simple import init as email_init
from thirtybirds_2_0.Adaptors.Cameras.elp import init as camera_init
from thirtybirds_2_0.Updates.manager import init as updates_init
from thirtybirds_2_0.Network.info import init as network_info_init

network_info = network_info_init()

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
DEVICES_PATH = "%s/Hosts/" % (BASE_PATH )
THIRTYBIRDS_PATH = "%s/thirtybirds_2_0" % (UPPER_PATH )
DISTORTION_MAP_PATH = os.path.join(BASE_PATH, "distortion_maps")

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)


########################
## CV HELPERS
########################

class CV_Helpers(object):
    def __init__(self):
        pass
    def read_image(self, path):
        return cv2.imread(path, -1)
    # Shows an image without the need to give a name or call waitkey.
    def show_image(self, image, title=None):
        if (title == None):
            title = show_image.window_counter
            show_image.window_counter += 1
        cv2.imshow(str(title), image)
        cv2.waitKey(0)
        #show_image.window_counter = 0 # scope this to class later

    def paste_transparent(self, background, foreground):
        image = background.copy()
        background_width, background_height, _ = background.shape
        foreground_width, foreground_height, _ = foreground.shape
        assert (background_height == foreground_height and background_width == foreground_width), "images must have equal dimensions"
        for x in xrange(background_width):
            for y in xrange(background_height):
                if foreground[x][y][3] != 0:
                    image[x][y] = (foreground[x][y][0], foreground[x][y][1], foreground[x][y][2])
        return image

    def gray_to_RGB(self, image):
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

    #def RGB_to_gray(self, image):
    #    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    #def LAB_CLAHE(self, image):
    #        output = image.copy()
    #        output = cv2.cvtColor(output, cv2.COLOR_BGR2LAB)
    #        l, a, b = cv2.split(output)
    #        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    #        l = clahe.apply(l)
    #        output = cv2.merge((l, a, b))
    #        output = cv2.cvtColor(output, cv2.COLOR_LAB2BGR)
    #        return output

    def draw_circles(self, image, circles):
        output = image.copy()
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                cv2.circle(output, (x, y), r, (0, 255, 0), 2)
            for (x, y, r) in circles:
                cv2.rectangle(output, (x - 2, y - 2), (x + 2, y + 2), (0, 128, 255), -1)
        return output

    #def flatten_color_regions(self, image):
    #        flattened = image.copy()
    #        for x, y in tuple((x, y) for x in range(image.shape[0]) for y in range(image.shape[1])):
    #            flattened[x][y] = [int(v/32)*32 for v in image[x][y]]
    #        return flattened

cv_helpers = CV_Helpers()

########################
## OBJECT DETECTION
########################

class Object_Detection(object):
    def __init__(self):
        pass

    def bottle_and_can_detection(self, image):
        #visualisation = image.copy()
        bottle_circles = self.bottle_detection( image )[1]
        can_circles = self.can_detection( image )[1]
        return bottle_circles, can_circles
        #visualisation = draw_circles( visualisation, bottle_circles )
        #visualisation = draw_circles( visualisation, can_circles )
        #circles = np.concatenate([bottle_circles[0], can_circles[0]])
        #return (circles, visualisation)

    def can_detection(self, image, max_circle_radius=200, draw_circles_on_processed=False):
        processed = image.copy()
        vis = image.copy()
        edges = cv2.Canny(processed, 150, 250, L2gradient=True, apertureSize=3)
        extendedWidth = edges.shape[0] + 2*max_circle_radius
        extendedHeight = edges.shape[1] + 2*max_circle_radius
        processed = np.zeros((extendedWidth, extendedHeight), np.uint8)
        processed[max_circle_radius:max_circle_radius + edges.shape[0], max_circle_radius:max_circle_radius + edges.shape[1]] = edges
        kernel = np.ones((3, 3), dtype="uint8")
        processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel)
        circles = cv2.HoughCircles(
            processed, 
            method=cv2.HOUGH_GRADIENT, 
            dp=3, 
            minDist=45,
            param1=250, 
            param2=200, 
            minRadius=45, 
            maxRadius=max_circle_radius
        )
        processed = cv_helpers.gray_to_RGB(processed)
        if (draw_circles_on_processed):
            processed = cv_helpers.draw_circles(processed, circles)
        circles = self.remove_border_from_circles(processed, circles, border=max_circle_radius)
        return processed, circles

    def remove_border_from_circles(self, image, circles, border, min_ratio=0.2):
        filtered_circles = []
        circled = image.copy()
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                filtered_circles += [[x-border, y-border, r]]
        return np.array([filtered_circles])

    def bottle_detection(self,  image, number_of_octaves=4 ):
        processed = image.copy()
        octaves = [ cv2.resize( processed, dsize=(0, 0), fx=1/float(x), fy=1/float(x), interpolation=cv2.INTER_LINEAR ) for x in range(1, number_of_octaves+1) ]
        octaves = map( lambda img: cv2.GaussianBlur(img, (5, 5), 0, 0), octaves )
        octaves = map( lambda img: cv2.Canny(img, 150, 250, L2gradient=True, apertureSize=3), octaves )
        octave_circles = map( 
                lambda i: cv2.HoughCircles(
                        octaves[i], 
                        method=cv2.HOUGH_GRADIENT, 
                        dp=2.8, 
                        minDist=45/(i+1), param1=250, param2=180/(i+1), 
                        minRadius=30/(i+1), 
                        maxRadius=60/(i+1)
                ),
                range(number_of_octaves) 
            )
        octaves = map( lambda img: cv_helpers.gray_to_RGB(img), octaves)
        circles = self.merge_octave_circles( octave_circles )
        circles = self.filter_octave_circles( circles )
        return processed, circles

    def merge_octave_circles(self, octave_circles):
        merged_circles = []
        for i in range(len(octave_circles)):
            if octave_circles[i] is not None:
                for (x, y, r) in octave_circles[i][0]:
                    merged_circles += [[x*(i+1), y*(i+1), r*(i+1)]]
        return np.array([merged_circles])

    def filter_octave_circles(self,  circles, identical_radius=0.3 ):
        filtered_circles = None
        if circles is not None:
            filtered_circles = []
            circles = np.round(circles[0, :]).astype("int")
            identical_candidates = self.find_identical_candidates(circles, identical_radius)

            identical_candidates_by_length = map( lambda (k, v): (k, len(v)), identical_candidates.iteritems())
            identical_candidates_by_length = sorted( identical_candidates_by_length, key=lambda circle: circle[1], reverse=True )

            circles_not_yet_clustered = map( lambda (k, v): k, identical_candidates.iteritems())
            for circle in identical_candidates_by_length:
                if (circle[0] in circles_not_yet_clustered):
                    filtered_circles += [(circle[0])]
                    for identical in identical_candidates[circle[0]]:
                        circles_not_yet_clustered = [icircle for icircle in circles_not_yet_clustered if icircle != identical]
                        
        return np.array([filtered_circles])

    def find_identical_candidates(self,  circles, identical_radius ):
        identical_candidates = {}
        for (x, y, r) in circles:
            identical_candidates[(x, y, r)] = []
            for (nx, ny, nr) in circles:
                distance_of_centers = math.sqrt((x-nx)**2 + (y-ny)**2)
                if ( 0 < distance_of_centers < r*identical_radius ):
                    identical_candidates[(x, y, r)] += [(nx, ny, nr)]

        return identical_candidates

########################
## LENS CORRECTION
########################

class Lens_Correction(object):
    def __init__(self, distortion_map):
        self.distortion_map = distortion_map

    def correct(self, distorted_image, scale=15):
        print "debug, correct,", 0
        image_width, image_height, _ = distorted_image.shape
        print "debug, correct,", 1
        map_width, map_height, _ = self.distortion_map.shape
        print "debug, correct,", 2

        assert (image_height == map_height and image_width ==map_width), "image and map must have equal dimensions"
        print "debug, correct,", 3
        distortion_points = []
        distortion_points_dict = {}
        distortion_point_locations = self.get_distortion_points()
        print "debug, correct,", 4
        for point in distortion_point_locations:
            distortion_points += [self.Distortion_Point(point[1], point[0], self.distortion_map)]
        print "debug, correct,", 5
        for point in distortion_points:
            distortion_points_dict[(point.real_coords_x, point.real_coords_y)] = point
        print "debug, correct,", 6
        min_real_x = min(map(lambda x: x[0], distortion_points_dict.keys()))
        max_real_x = max(map(lambda x: x[0], distortion_points_dict.keys()))
        min_real_y = min(map(lambda x: x[1], distortion_points_dict.keys()))
        max_real_y = max(map(lambda x: x[1], distortion_points_dict.keys()))
        print "debug, correct,", 7
        undistorted_image = np.zeros(((max_real_y-min_real_y)*scale, (max_real_x-min_real_x)*scale, 3), np.uint8)
        print "debug, correct,", 8
        for x in range(min_real_x, max_real_x, 10):
            for y in range(min_real_y, max_real_y, 10):
                min_x = x
                min_y = y
                max_x = x+10
                max_y = y+10
                if min_y == 80:
                    max_y = 85
                undistorted_minimal_square = self.undistort_minimal_square(distorted_image, distortion_points_dict, min_x, min_y, max_x, max_y, scale=scale)
                undistorted_image[(min_y-min_real_y)*scale:(max_y-min_real_y)*scale, (min_x-min_real_x)*scale:(max_x-min_real_x)*scale] = undistorted_minimal_square
        print "debug, correct,", 10
        return undistorted_image

    # This function takes in the manually created distortion map, finds the
    # center points of all the circles and returns those in a list

    def get_distortion_points(self):
        distortion_points = []
        width, height, channels = self.distortion_map.shape
        assert channels == 4, "Your so-called distortion map doesn't have transparency. There's a fair chance you did something wrong, mate"
        flattened_image = np.ones((width, height, 3), np.uint8)
        flattened_image = flattened_image * 255
        flattened_image = cv_helpers.paste_transparent(flattened_image, self.distortion_map)
        detector = cv2.SimpleBlobDetector_create()
        keypoints = detector.detect(flattened_image)
        distortion_points = map(lambda x: (int(x.pt[0]), int(x.pt[1])), keypoints)
        return distortion_points

    # Perspective warps a minimal square - Nothing to it, really.
    # There's some heavy optimizing potential here, if desired: During a 'compilation' step, save all the transformMatrices.
    # Then you could skip everything in between opening the image and the
    # warpPerspective call.

    def undistort_minimal_square(self, distorted_image, distortion_points, min_x, min_y, max_x, max_y, scale=15):
        lowerLeft = distortion_points[(min_x, min_y)].getLocation()
        upperLeft = distortion_points[(max_x, min_y)].getLocation()
        lowerRight = distortion_points[(min_x, max_y)].getLocation()
        upperRight = distortion_points[(max_x, max_y)].getLocation()
        originPoints = np.float32([upperLeft, upperRight, lowerLeft, lowerRight])
        targetPoints = np.float32([[(max_x-min_x)*scale, 0], [(max_x-min_x)*scale, (max_y-min_y)*scale], [0, 0], [0, (max_y-min_y)*scale]])
        transformMatrix = cv2.getPerspectiveTransform(originPoints, targetPoints)
        undistorted_image = cv2.warpPerspective(
            src=distorted_image, M=transformMatrix, dsize=((max_x-min_x)*scale, (max_y-min_y)*scale))
        return undistorted_image

    class Distortion_Point(object):
        def __init__(self, x, y, image):
            self.x = x
            self.y = y
            self.real_coords_x = image[x][y][2]
            self.real_coords_y = image[x][y][1]

        def output(self):
            print self.x, self.y, self.real_coords_x, self.real_coords_y

        def getLocation(self):
            return [self.y, self.x]




########################
## CAMERA TO SHELF SPATIAL MAPPING
########################

class Camera_To_Shelf_Spatial_Mapping(object):
    def __init__(self, shelf, camera):
        self.shelf = shelf
        self.camera = camera
        self.upper_shelf_image_points = None
        self.lower_shelf_image_points = None
        self.world_points = None
        self.map_folder = "Location Maps/"
        self.upper_shelf_height = 20.5
        self.lower_shelf_height = 12.5
        self.init_maps()

    def init_maps(self):
        upper_shelf_path = self.map_folder + self.shelf + "_" + str(self.upper_shelf_height) + "_" + str(self.camera) + ".png"
        lower_shelf_path = self.map_folder + self.shelf + "_" + str(self.lower_shelf_height) + "_" + str(self.camera) + ".png"
        upper_shelf_image = cv_helpers.read_image( upper_shelf_path )
        lower_shelf_image = cv_helpers.read_image( lower_shelf_path )
        self.upper_shelf_image_points = self.init_map_points( upper_shelf_image )
        self.lower_shelf_image_points = self.init_map_points( lower_shelf_image )
        self.init_world_points( upper_shelf_image )

    def init_map_points(self, location_map):
      width, height, channels = location_map.shape
      assert channels == 4, "Your location map doesn't have transparency. That sounds wrong"
      flattened_image = np.ones((width, height, 3), np.uint8)
      flattened_image = flattened_image * 255
      flattened_image = cv_helpers.paste_transparent(flattened_image, location_map)
      detector = cv2.SimpleBlobDetector_create()
      keypoints = detector.detect(flattened_image)
      if ( len(keypoints) is not 2):
        raise Value_Error("When initializing location maps, an incorrect number of keypoints has been found. There should be only two.")
      top_left_pixel = keypoints[0].pt if keypoints[0].pt[0] < keypoints[1].pt[0] else keypoints[1].pt
      bottom_right_pixel = keypoints[1].pt if keypoints[0].pt[0] < keypoints[1].pt[0] else keypoints[0].pt
      top_left_pixel = (int(top_left_pixel[0]) , int(top_left_pixel[1]))
      bottom_right_pixel = (int(bottom_right_pixel[0]), int(bottom_right_pixel[1]))
      return (top_left_pixel, bottom_right_pixel)

    def init_world_points(self, location_map):
      if ( self.upper_shelf_image_points is None or self.lower_shelf_image_points is None ):
        raise Error("Image map points are initialized incorrectly")
      upx = self.upper_shelf_image_points[0][1]
      upy = self.upper_shelf_image_points[0][0]
      downx = self.upper_shelf_image_points[1][1]
      downy = self.upper_shelf_image_points[1][0]
      up_color = location_map[upx][upy]
      down_color = location_map[downx][downy]
      self.world_points = ((up_color[1], up_color[2]), (down_color[1], down_color[2]))

    def location_on_upper_plane(self, x, y):
      distance_between_reference_points_x = self.upper_shelf_image_points[1][0] - self.upper_shelf_image_points[0][0]
      distance_between_reference_points_y = self.upper_shelf_image_points[1][1] - self.upper_shelf_image_points[0][1]
      distance_between_world_points_x = self.world_points[1][1] - self.world_points[0][1]
      distance_between_world_points_y = self.world_points[1][0] - self.world_points[0][0]
      x_offset_to_top_left_point = x - self.upper_shelf_image_points[0][0]
      y_offset_to_top_left_point = y - self.upper_shelf_image_points[0][1]
      x_offset_relative = x_offset_to_top_left_point / float(distance_between_reference_points_x)
      y_offset_relative = y_offset_to_top_left_point / float(distance_between_reference_points_y)
      x = int( self.world_points[0][1] + x_offset_relative * distance_between_world_points_x)
      y = int( self.world_points[0][0] + y_offset_relative * distance_between_world_points_y)
      return (x, y)

    def location_on_lower_plane(self, x, y):
      distance_between_reference_points_x = self.lower_shelf_image_points[1][0] - self.lower_shelf_image_points[0][0]
      distance_between_reference_points_y = self.lower_shelf_image_points[1][1] - self.lower_shelf_image_points[0][1]
      distance_between_world_points_x = self.world_points[1][1] - self.world_points[0][1]
      distance_between_world_points_y = self.world_points[1][0] - self.world_points[0][0]
      x_offset_to_top_left_point = x - self.lower_shelf_image_points[0][0]
      y_offset_to_top_left_point = y - self.lower_shelf_image_points[0][1]
      x_offset_relative = x_offset_to_top_left_point / float(distance_between_reference_points_x)
      y_offset_relative = y_offset_to_top_left_point / float(distance_between_reference_points_y)
      x = int( self.world_points[0][1] + x_offset_relative * distance_between_world_points_x)
      y = int( self.world_points[0][0] + y_offset_relative * distance_between_world_points_y)
      return (x, y)

    def get_real_world_location( self, image_x, image_y, height ):
      location_upper = self.location_on_upper_plane( image_x, image_y )
      location_lower = self.location_on_lower_plane( image_x, image_y )
      distance_between_reference_real_x = location_upper[0] - location_lower[0]
      distance_between_reference_real_y = location_upper[1] - location_lower[1]
      distance_between_reference_real_z = self.upper_shelf_height - self.lower_shelf_height
      z_offset_to_bottom = height - self.lower_shelf_height
      z_offset_relative = z_offset_to_bottom / float( distance_between_reference_real_z )
      x = int( location_lower[0] + distance_between_reference_real_x * z_offset_relative )
      y = int( location_lower[1] + distance_between_reference_real_y * z_offset_relative )
      z = height
      return (x, y, z)

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
        return "{}_{}_{}_{}_{}.png".format(timestamp, self.get_shelf_id() ,  self.get_camera_id(), light_level, process_type) 

    def remote_update_git(self, supercooler, thirtybirds, update, upgrade):
        if supercooler:
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/supercooler')
        if thirtybirds:
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/thirtybirds_2_0')
        return 

    def remote_update_scripts(self):
        updates_init("/home/pi/supercooler", False, True)
        return

    def get_update_script_version(self):
        (updates, ghStatus, bsStatus) = updates_init("/home/pi/supercooler", False, False)
        return updates.read_version_pickle()

    def get_git_timestamp(self):
        return commands.getstatusoutput("cd /home/pi/supercooler/; git log -1 --format=%cd")[1]   

    def get_client_status(self):
        return (self.hostname, self.get_update_script_version(), self.get_git_timestamp())

########################
## IMAGES
########################

class Images(object):
    def __init__(self, capture_path):
        self.capture_path = capture_path
        self.camera = camera_init(self.capture_path)

    def capture_image(self, filename):
        self.camera.take_capture(filename)

    def get_capture_filenames(self):
        return [ filename for filename in os.listdir(self.capture_path) if filename.endswith(".png") ]

    def delete_captures(self):
        previous_filenames = self.get_capture_filenames()
        for previous_filename in previous_filenames:
            os.remove("{}{}".format(self.capture_path,  previous_filename))

    def get_values_from_filename(self, filename):
        shelf_id = filename[:-4][:1]
        camera_id = filename[1:-6]
        light_level = filename[:-8][-1:]
        return shelf_id, camera_id, light_level

    def get_capture_filepaths(self):
        filenames = self.get_capture_filenames()
        return list(map((lambda filename:  os.path.join(self.capture_path, filename)), filenames))
        #return [ os.path.join(self.capture_path, current_filename) for current_filename in os.listdir(self.capture_path) if current_filename.endswith(".png") ]

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
            subprocess.Popen(['gdrive', 'upload', '-p', google_drive_directory_id, filepath])
        except Exception as e:
            print "exception in Network.copy_to_gdrive", e
                

########################
## DATA 
########################

class Data(object):
    def __init__(self, shelf_id, camera_id):
        self. shelf_id = shelf_id
        self.camera_id = camera_id
    def create_blank_potential_object(self, object_type, camera_x, camera_y, radius):
            return {
                "shelf_id":self.shelf_id,
                "camera_id":self.camera_id,
                "object_type": object_type, 
                "camera_x":camera_x,
                "camera_y":camera_y,
                "radius":radius
            }

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
        self.distortion_map_dir = os.path.join(DISTORTION_MAP_PATH, self.utils.get_shelf_id(), self.utils.get_camera_id())
        self.distortion_map_names = ["125.png", "205.png", "220.png", "230.png", "240.png"]
        self.object_detection = Object_Detection()
        self.data = Data(self.utils.get_shelf_id(), self.utils.get_camera_id())

        distortion_map_ocv = cv_helpers.read_image(os.path.join(self.distortion_map_dir, self.distortion_map_names[4])) 
        self.lens_correction = Lens_Correction(distortion_map_ocv)

        self.network.thirtybirds.subscribe_to_topic("reboot")
        self.network.thirtybirds.subscribe_to_topic("remote_update")
        self.network.thirtybirds.subscribe_to_topic("remote_update_scripts")
        self.network.thirtybirds.subscribe_to_topic("capture_image")
        self.network.thirtybirds.subscribe_to_topic("client_monitor_request")
        self.network.thirtybirds.subscribe_to_topic("capture_and_upload")
        self.network.thirtybirds.subscribe_to_topic("perform_object_detection")
        self.network.thirtybirds.subscribe_to_topic("process_images_and_report")
        #self.network.thirtybirds.subscribe_to_topic(HOSTNAME)
        #self.network.thirtybirds.subscribe_to_topic("return_raw_images")
        #self.network.thirtybirds.subscribe_to_topic("parse_and_annotate")
        #self.camera = camera_init(self.capture_path)


    def network_message_handler(self, topic_msg):
        # this method runs in the thread of the caller, not the tread of Main

        topic, msg =  topic_msg # separating just to eval msg.  best to do it early.  it should be done in TB.
        if topic not in  ["client_monitor_request"]:
            print "Main.network_message_handler", topic_msg
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
                #print "main.run topic=",repr(topic)
                #print "main.run msg=",repr(msg)
                if topic == "reboot":
                    self.utils.reboot()

                if topic == "remote_update":
                    supercooler, thirtybirds, update, upgrade = msg
                    self.utils.remote_update_git(supercooler, thirtybirds, update, upgrade)
                    self.network.thirtybirds.send("update_complete", self.hostname)

                if topic == "remote_update_scripts":
                    self.utils.remote_update_scripts()
                    self.network.thirtybirds.send("update_complete", self.hostname)

                if topic == "capture_image":
                    light_level, timestamp = msg
                    #if light_level in [0, "0"]: # on request 0, empty directory
                    self.images.delete_captures()
                    filename = self.utils.create_image_file_name(timestamp, light_level, "raw")
                    self.images.capture_image(filename)

                if topic == "client_monitor_request":
                    self.network.thirtybirds.send("client_monitor_response", self.utils.get_client_status())

                if topic == "capture_and_upload":
                    print msg
                    print repr(msg)
                    timestamp, light_level, google_drive_directory_id, clear_dir = msg
                    if clear_dir: self.images.delete_captures()
                    filename = self.utils.create_image_file_name(timestamp, light_level, "raw")
                    self.images.capture_image(filename)
                    #self.network.copy_to_gdrive(google_drive_directory_id, os.path.join(self.capture_path, filename))

                if topic in ["perform_object_detection", "process_images_and_report"]:
                    potential_objects = []
                    for filepath in self.images.get_capture_filepaths():
                        print "main.run opening capture"
                        capture_raw_ocv = cv_helpers.read_image(filepath)
                        print "main.run performing lens correction"
                        capture_corrected_ocv = self.lens_correction.correct(capture_raw_ocv)
                        print "main.run bottle detection"
                        capture_with_bottles_ocv, bottle_circles = self.object_detection.bottle_detection( capture_corrected_ocv )
                        print "main.run can detection"
                        capture_with_cans_ocv, can_circles = self.object_detection.can_detection( capture_corrected_ocv )
                        print "debug:"
                        print can_circles
                        print "main.run collecting object  data"
                        #print can_circles[0]
                        #print repr(can_circles[0][0])
                        if len(bottle_circles) > 0:
                            for bottle_circle in bottle_circles[0]:
                                potential_objects.append( self.data.create_blank_potential_object("bottle", bottle_circle[0], bottle_circle[1], bottle_circle[2] ))
                        
                        if len(can_circles) > 0:
                            for can_circle in can_circles[0]:
                                potential_objects.append( self.data.create_blank_potential_object("can", bottle_circle[0], bottle_circle[1], bottle_circle[2] )) 
                    self.network.thirtybirds.send(
                        "receive_image_data", 
                        {
                            "shelf_id":self.utils.get_shelf_id(),
                            "camera_id":self.utils.get_camera_id(),
                            "potential_objects":potential_objects,
                            "undistorted_capture_ocv":cv2.imencode('.png', capture_corrected_ocv)[1].tostring()
                        }
                    )


                #if topic == "process_images_and_report":
                #if topic == self.hostname:
                #if topic == "return_raw_images":
                #if topic == "capture_and_upload":
                #if topic == "parse_and_annotate":
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print e, repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

########################
## INIT
########################

def init(HOSTNAME):
    main = Main(HOSTNAME)
    main.daemon = True
    main.start()
    return main
