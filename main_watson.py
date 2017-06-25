# single - unit image cap using watson
#sys.path.append('/usr/local/lib/python2.7/site-packages')
#sys.path.append('/home/pi/.virtualenvs/cv/lib/python2.7/site-packages')

import commands
import cv2
import datetime
import json
import math
import numpy as np
import os
from os import environ
from os import walk
from os.path import join, dirname
import shutil
import sys
import time

from watson_developer_cloud import VisualRecognitionV3
#from parser import Image_Parser

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPPER_PATH = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
DEVICES_PATH = "%s/Hosts/" % (BASE_PATH )
THIRTYBIRDS_PATH = "%s/thirtybirds" % (UPPER_PATH )

sys.path.append(BASE_PATH)
sys.path.append(UPPER_PATH)

from thirtybirds_2_0.Adaptors.Cameras.elp import init as camera_init
#from Roles.camera_units.imageparser import  ImageParser 
# take capture

capture_path = "/home/pi/supercooler/Captures/"
camera = camera_init(capture_path)

filenames = ["test1.png","test2.png","test3.png"]
for filename in filenames:
    camera.take_capture(filename)
    time.sleep(1)

# run object detection

class ImageParser(): # class not necessary.  used for organization
    def __init__(self):
        self.parsedCaptures = [] # 2D list of capture:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        self.foldername = ("%s/ParsedCaptures") %(dir_path)
        #os.makedirs(self.foldername)
    def empty_directory(self):
        for file in os.listdir(self.foldername):
            file_path = os.path.join(self.foldername, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path): shutil.rmtree(file_path)
            except Exception as e:
                print(e)

    def get_foldername(self):
        return self.foldername

    def get_parsed_images(self):
        return self.parsedCaptures

    def undistort_image(self, image):
        width = image.shape[1]
        height = image.shape[0]
        distCoeff = np.zeros((4,1),np.float64)
        k1 = -6.0e-5; # negative to remove barrel distortion
        k2 = 0.0;
        p1 = 0.0;
        p2 = 0.0;
        distCoeff[0,0] = k1;
        distCoeff[1,0] = k2;
        distCoeff[2,0] = p1;
        distCoeff[3,0] = p2;
        # assume unit matrix for camera
        cam = np.eye(3,dtype=np.float32)
        cam[0,2] = width/2.0  # define center x
        cam[1,2] = height/2.0 # define center y
        cam[0,0] = 10.        # define focal length x
        cam[1,1] = 10.        # define focal length y
        # here the undistortion will be computed
        return cv2.undistort(image,cam,distCoeff)

    def adjust_gamma(self, image, gamma=1.0):
        # build a lookup table mapping the pixel values [0, 255] to
        # their adjusted gamma values
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
     
        # apply gamma correction using the lookup table
        return cv2.LUT(image, table)

    def process_image(self, filepath, camera_id, offset_x, offset_y):
        print "Processing image...", camera_id, filepath
        parsedImageMetadata = [] 
        self.parsedCaptures.append(parsedImageMetadata)# images are introduce in order of cap_id, so list index == cap_id
        img_for_cropping = cv2.imread(filepath) # read image into memory
        print 
        img_for_cropping = cv2.resize(img_for_cropping, (800,450), cv2.INTER_AREA) # resize image
        img_for_cropping = self.undistort_image(img_for_cropping) # get unbent!

        img_for_circle_detection = cv2.imread(filepath,0) # read image into memory
        img_for_circle_detection = cv2.resize(img_for_circle_detection, (800,450), cv2.INTER_AREA) # resize image
        img_for_circle_detection = self.undistort_image(img_for_circle_detection) # get unbent!
        height, width = img_for_circle_detection.shape

        img_for_circle_detection = cv2.medianBlur(img_for_circle_detection,21)
        img_for_circle_detection = cv2.blur(img_for_circle_detection,(1,1))

        img_for_circle_detection = cv2.Canny(img_for_circle_detection, 0, 23, True)
        img_for_circle_detection = cv2.adaptiveThreshold(img_for_circle_detection,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,17,2)

        print "Detecting circles..."
        circles = cv2.HoughCircles(img_for_circle_detection,cv2.HOUGH_GRADIENT,1,150, param1=70,param2=28,minRadius=30,maxRadius=80)

        margin = 30
        if circles is not None:
            # convert the (x, y) coordinates and radius of the circles to integers
            _circles = np.round(circles[0, :]).astype("int")
         
            # loop over the (x, y) coordinates and radius of the circles
            for (x, y, radius) in _circles:
                # draw the circle in the output image, then draw a rectangle
                    # corresponding to the center of the circle
                leftEdge = x-radius-margin if x-radius-margin >= 0 else 0
                rightEdge = x+radius+margin if x+radius+margin <= width else width
                topEdge = y-radius-margin if y-radius-margin >=0 else 0
                bottomEdge = y+radius+margin if y+radius+margin <= height else height

                #cv2.circle(img_for_circle_detection, (x, y), radius, (255, 0, 0), 10)
                cv2.rectangle(img_for_circle_detection, (leftEdge, topEdge), (rightEdge, bottomEdge), (0, 128, 255), -1)
         

                testFileName = "{}_4_with_circles.png".format(camera_id)
                cv2.imwrite(testFileName ,img_for_circle_detection)
        testFileName = "{}_0_croppingTest.png".format(camera_id)
        cv2.imwrite(testFileName ,img_for_cropping) 

        circles = np.uint16(np.around(circles))
        margin = 30
        for x, y, radius in circles[0,:]:
            x=int(x)
            y=int(y)
            radius=int(radius)
            leftEdge = x-radius-margin if x-radius-margin >= 0 else 0
            rightEdge = x+radius+margin if x+radius+margin <= width else width
            topEdge = y-radius-margin if y-radius-margin >=0 else 0
            bottomEdge = y+radius+margin if y+radius+margin <= height else height
            crop_img = img_for_cropping[topEdge:bottomEdge, leftEdge:rightEdge]
            imageName = 'image_%s_%s_%s.jpg'%(camera_id,x, y)
            pathName = '%s/%s'%(self.foldername, imageName)
            cv2.imwrite(pathName,crop_img)
            # draw the outer circle
            cv2.circle(img_for_cropping,(x,y),radius,(0,255,0),2)
            # draw the center of the circle
            cv2.circle(img_for_cropping,(x,y),2,(0,0,255),3)
            #print len(circles)
            totalX = x + offset_x
            totalY = y + offset_y
            parsedImageMetadata.append( {
                'capture':camera_id,
                'imageName':imageName,
                'pathName':pathName,
                'x':x,
                'y':y,
                'totalX':totalX,
                'totalY':totalY,
                'radius':radius,
                'leftEdge':leftEdge,
                'rightEdge':rightEdge,
                'topEdge':topEdge,
                'bottomEdge':bottomEdge,
                'label':"",
                'confidence':0,
                'duplicate':False
            } )
            #print "detected circle:", repr(x), repr(y), repr(radius), leftEdge, rightEdge, topEdge, bottomEdge
        # cv2.imshow('detected circles',img_for_cropping)
        #cv2.destroyAllWindows()
        #print parsedImageMetadata
        print "Processing image done"

    def processImages(self, captureLIst):
        self.parsedCaptures = [] # 2D list of capture:
        self.empty_directory()
        for index, cap_metadata in enumerate(captureLIst):
            self.process_image(cap_metadata[0],index, cap_metadata[1], cap_metadata[2])


capture_list = [["test1.png",0,0],["test2.png",0,0],["test3.png",0,0]]

imageparser = ImageParser()
print ">>>> 1"
imageparser.processImages(capture_list)
print ">>>> 2"
parsed_images = imageparser.get_parsed_images()
print ">>>> 3", parsed_images
parsed_folder_name = imageparser.get_foldername()
print ">>>> 4", parsed_folder_name

# collect capture data to be send to conductor


# parse capture into cropped images




# prepare images for watson




# send to watson




# print results






