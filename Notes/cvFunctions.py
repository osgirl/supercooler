import math
import cv2
import numpy as np


############################
# 0. BASIC HELPER FUNCTIONS#
############################


# Reads an image without the need to specify a color space.
# Always uses the images original color space
def read_image(path):
    return cv2.imread(path, -1)


# Shows an image without the need to give a name or call waitkey.
def show_image(image, title=None):
    if (title == None):
        title = show_image.window_counter
        show_image.window_counter += 1
    cv2.imshow(str(title), image)
    cv2.waitKey(0)
show_image.window_counter = 0


# A fairly slow, but easy to understand algorithm to paste a partially transparent
# 4-channel image onto a standard 3-channel image
def paste_transparent(background, foreground):
    image = background.copy()
    background_width, background_height, _ = background.shape
    foreground_width, foreground_height, _ = foreground.shape
    assert (background_height == foreground_height and background_width ==
            foreground_width), "images must have equal dimensions"

    for x in xrange(background_width):
        for y in xrange(background_height):
            if foreground[x][y][3] != 0:
                image[x][y] = (foreground[x][y][0], foreground[
                               x][y][1], foreground[x][y][2])

    return image


def gray_to_RGB(image):
    return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)


def RGB_to_gray(image):
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)


def LAB_CLAHE(image):
    output = image.copy()
    output = cv2.cvtColor(output, cv2.COLOR_BGR2LAB)

    l, a, b = cv2.split(output)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    output = cv2.merge((l, a, b))

    output = cv2.cvtColor(output, cv2.COLOR_LAB2BGR)
    return output


def draw_circles(image, circles):
    output = image.copy()
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")

        for (x, y, r) in circles:
            cv2.circle(output, (x, y), r, (0, 255, 0), 2)

        for (x, y, r) in circles:
            cv2.rectangle(output, (x - 2, y - 2),
                          (x + 2, y + 2), (0, 128, 255), -1)

    return output


def flatten_color_regions(image):
    flattened = image.copy()
    for x, y in tuple((x, y) for x in range(image.shape[0]) for y in range(image.shape[1])):
        flattened[x][y] = [int(v/32)*32 for v in image[x][y]]

    return flattened

#################################################################
# 1. LENS CORRECTIONS
#   1.1 basic_af_lens_correction()
#     Just don't use this. It was an initial quick prototype
#   1.2 mapped_lens_correction()
#     Quality algorithm based on a handmade map of grid lattices.
#   1.3 Panorama
#     Impelements early stages of SIFT feature detection
#     Great in general, not suitable for this problem.
#################################################################

#
# 1.1 basic_af_lens_correction()
# Deprecated
#

# This algorithm is very minimalistic, based on trig, assumes the center of the distrotion to be at the image center etc,
# Try strength = 2, zoom = 1 and go from there
# Or just skip to a better system


def basic_af_lens_correction(image, strength, zoom):
    assert strength >= 0.0, "Strength needs to be >= 0"
    assert zoom >= 1.0, "Zoom needs to be >= 1"

    undistorted = image.copy()
    width, height, depth = image.shape

    half_width = width/2
    half_height = height/2

    correctionRadius = math.sqrt(width**2 + height**2)/strength

    for x in xrange(width):
        for y in xrange(height):
            newX = x - half_width
            newY = y - half_height
            distance = math.sqrt(newX**2 + newY**2)
            r = distance / correctionRadius

            if r == 0:
                theta = 1
            else:
                theta = np.arctan(r) / r

            sourceX = int(half_width+theta*newX*zoom)
            sourceY = int(half_height+theta*newY*zoom)

            if (0 < sourceX < width and 0 < sourceY < height):
                undistorted[x, y] = image[sourceX][sourceY]
            else:
                undistorted[x, y] = (0, 0, 0)

    return undistorted


#
# 1.2 mapped_lens_correction()
#

# Main function of undisturbing images based on their handmade distortion map
# Just call this function - everything else in here is a helper and doesn't need to be called directly.
# This contains some remaining magic numbers:
#   1. The step size of 10 (based on the values I used to encode location
#   which increase by 10 in the red/green channel along the x/y-axis _of the grid_, not the image)
#   2. The hardcoded max_y of 85, based on the fact that the grid doesn't
#   height isn't a multiple of 2, but the min-squares are
def mapped_lens_correction(distorted_image, distortion_map, scale=15):
    image_width, image_height, _ = distorted_image.shape
    map_width, map_height, _ = distortion_map.shape

    assert (image_height == map_height and image_width ==
            map_width), "image and map must have equal dimensions"

    distortion_points = []
    distortion_points_dict = {}
    distortion_point_locations = get_distortion_points(distortion_map)

    for point in distortion_point_locations:
        distortion_points += [Distortion_Point(point[1], point[0], distortion_map)]

    for point in distortion_points:
        distortion_points_dict[(point.real_coords_x, point.real_coords_y)] = point

    min_real_x = min(map(lambda x: x[0], distortion_points_dict.keys()))
    max_real_x = max(map(lambda x: x[0], distortion_points_dict.keys()))
    min_real_y = min(map(lambda x: x[1], distortion_points_dict.keys()))
    max_real_y = max(map(lambda x: x[1], distortion_points_dict.keys()))

    print 'min_real_x', min_real_x, 'min_real_y', min_real_y
    print 'max_real_x', max_real_x, 'max_real_y', max_real_y

    undistorted_image = np.zeros(
        ((max_real_y-min_real_y)*scale, (max_real_x-min_real_x)*scale, 3), np.uint8)

    for x in range(min_real_x, max_real_x, 10):
        for y in range(min_real_y, max_real_y, 10):
            min_x = x
            min_y = y
            max_x = x+10
            max_y = y+10
            if min_y == 80: max_y = 85

            undistorted_minimal_square = undistort_minimal_square(
                distorted_image, distortion_points_dict, min_x, min_y, max_x, max_y, min_real_x, max_real_x, min_real_y, max_real_y, scale=scale)

            row_start = (min_y-min_real_y)*scale
            row_end   = (max_y-min_real_y)*scale
            col_start = (min_x-min_real_x)*scale
            col_end   = (max_x-min_real_x)*scale

            undistorted_image[row_start:row_end, col_start:col_end] = undistorted_minimal_square
            #show_image(undistorted_image, 'ef')

    #cv2.circle(undistorted_image, ((10                      )*scale, (10                      )*scale), 15, (255,0,0), 2)
    #cv2.circle(undistorted_image, ((max_real_x-10-min_real_x)*scale, (max_real_y-10-min_real_y)*scale), 15, (0,255,0), 2)
    return undistorted_image

# This function takes in the manually created distortion map, finds the
# center points of all the circles and returns those in a list


def get_distortion_points(distortion_map):
    distortion_points = []
    width, height, channels = distortion_map.shape
    assert channels == 4, "Your so-called distortion map doesn't have transparency. There's a fair chance you did something wrong, mate"
    flattened_image = np.ones((width, height, 3), np.uint8)
    flattened_image = flattened_image * 255
    flattened_image = paste_transparent(flattened_image, distortion_map)

    detector = cv2.SimpleBlobDetector_create()
    keypoints = detector.detect(flattened_image)

    distortion_points = map(lambda x: (int(x.pt[0]), int(x.pt[1])), keypoints)

    return distortion_points

# Perspective warps a minimal square - Nothing to it, really.
# There's some heavy optimizing potential here, if desired: During a 'compilation' step, save all the transformMatrices.
# Then you could skip everything in between opening the image and the
# warpPerspective call.


def undistort_minimal_square(distorted_image, distortion_points, min_x, min_y, max_x, max_y, min_real_x, max_real_x, min_real_y, max_real_y, scale=15):
    lowerLeft  = distortion_points[(min_x, min_y)].getLocation()
    upperLeft  = distortion_points[(max_x, min_y)].getLocation()
    lowerRight = distortion_points[(min_x, max_y)].getLocation()
    upperRight = distortion_points[(max_x, max_y)].getLocation()

    image_width, image_height, _ = distorted_image.shape

    if min_x == min_real_x and min_x != 0:
        lowerLeft [1] = min( lowerLeft[1]+100, image_width)
        lowerRight[1] = min(lowerRight[1]+100, image_width)

    if min_y == min_real_y and min_y !=0:
        lowerLeft[0] = 0
        upperLeft[0] = 0

    if max_x == max_real_x and max_x != 110:
        upperLeft [1] = 0
        upperRight[1] = 0

    if max_y == max_real_y and max_y != 85:
        lowerRight[0] = min(lowerRight[0]+100, image_height)
        upperRight[0] = min(upperRight[0]+100, image_height)

    originPoints = np.float32([upperLeft, upperRight, lowerLeft, lowerRight])
    targetPoints = np.float32([[(max_x-min_x)*scale, 0], [(max_x-min_x)*scale, (max_y-min_y)*scale], [
                              0, 0], [0, (max_y-min_y)*scale]])

    transformMatrix = cv2.getPerspectiveTransform(originPoints, targetPoints)

    undistorted_image = cv2.warpPerspective(
        src=distorted_image, M=transformMatrix, dsize=((max_x-min_x)*scale, (max_y-min_y)*scale))

    #show_image(undistorted_image, "sdf")

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


# 1.3 Panorama
# Briefly attempted to use feature description to stitch all images together.
# Unfortunately, every can and bottle is almost completely round
# and the things that are edges (like lettering) are not unique
# In other words, this problem is a prime example of what not to use SIFT/variants for.
#
# Deprecated. But you can use it to panorama your travel pictures if you like.

class Panorama(object):

    def __init__(self):
        pass

    def stitch(self, images, ratio=0.75, reprojThresh=4.0, show_matches=False):
        panorama = np.zeros((5000, 5000, 3), np.uint8)
        panorama[0:images[0].shape[0], 0:images[0].shape[1]] = images[0]

        # stitch first image
        imageA, imageB = images[0], images[1]
        keypointsA, features0 = self.detect_and_describe(imageA)
        keypointsB, features1 = self.detect_and_describe(imageB)

        M = self.match_keypoints(
            keypointsA, keypointsB, features0, features1, ratio, reprojThresh)

        if M is None:
            return None

        (matches, H, status) = M
        sumWidth = imageA.shape[1] + imageB.shape[1]
        sumHeight = imageA.shape[0] + imageB.shape[0]

        result = cv2.warpPerspective(imageA, H, (sumWidth, sumHeight))
        result[0:imageB.shape[0], 0:imageB.shape[1]] = imageB

        if show_matches:
            vis = self.draw_matches(
                imageA, imageB, keypointsA, keypointsB, matches, status)
            return (result, vis)

        return result

    def detect_and_describe(self, image):
        image = RGB_to_gray(image)
        detector = cv2.FeatureDetector_create("SIFT")
        keypoints = detector.detect(image)
        extractor = cv2.DescriptorExtractor_create("SIFT")
        (keypoints, features) = extractor.compute(image, keypoints)
        keypoints = np.float32([kp.pt for kp in keypoints])

        return (keypoints, features)

    def match_keypoints(self, kpsA, kpsB, featuresA, featuresB,
                        ratio, reprojThresh):
        matcher = cv2.DescriptorMatcher_create("BruteForce")
        rawMatches = matcher.knnMatch(featuresA, featuresB, 2)
        matches = []

        for m in rawMatches:

            if len(m) == 2 and m[0].distance < m[1].distance * ratio:
                matches.append((m[0].trainIdx, m[0].queryIdx))

        if len(matches) > 4:

            ptsA = np.float32([kpsA[i] for (_, i) in matches])
            ptsB = np.float32([kpsB[i] for (i, _) in matches])

            (H, status) = cv2.findHomography(ptsA, ptsB, cv2.RANSAC,
                                             reprojThresh)

            return (matches, H, status)

        return None

    def draw_matches(self, imageA, imageB, kpsA, kpsB, matches, status):
        # initialize the output visualization image
        (hA, wA) = imageA.shape[:2]
        (hB, wB) = imageB.shape[:2]
        vis = np.zeros((max(hA, hB), wA + wB, 3), np.uint8)
        vis[0:hA, 0:wA] = imageA
        vis[0:hB, wA:] = imageB

        # loop over the matches
        for ((trainIdx, queryIdx), s) in zip(matches, status):
            # only process the match if the keypoint was successfully
            # matched
            if s == 1:
                # draw the match
                ptA = (int(kpsA[queryIdx][0]), int(kpsA[queryIdx][1]))
                ptB = (int(kpsB[trainIdx][0]) + wA, int(kpsB[trainIdx][1]))
                cv2.line(vis, ptA, ptB, (0, 255, 0), 1)

        # return the visualization
        return vis


####################################################################
# 2. DETECTION
#   2.0 bottle_and_can_detection():
#     Use this method to get maximum detection (with quite a few false positives)
#   2.1 can_detection()
#     Use this to detect cans. It might also find bottles and noise.
#   2.2 bottle_detection()
#     Use this to detect bottles. It might also find cans and noise.
#   2.3 remove_border_from_circles()
#     Rectifies the extended border created before the circle detection
####################################################################



def bottle_and_can_detection( image ):
    visualisation = image.copy()
    bottle_circles = bottle_detection( image )[1]
    can_circles = can_detection( image )[1]

    visualisation = draw_circles( visualisation, bottle_circles )
    visualisation = draw_circles( visualisation, can_circles )

    circles = np.concatenate([bottle_circles[0], can_circles[0]])

    return (circles, visualisation)

# 2.1 can_detection()
#
# Optimised to detect beverage cans.
#
# Inputs:
#   image: Image to run detection on
#   max_circle_radius: Quite simply the maximum radius of the detected circles.
#   This should probably not be changed; It's mostly used as a standard argument
#   to support searching for circles touching the image bounds.
# Outputs:
#   (output, vis, circles)

def can_detection(image, max_circle_radius=100, draw_circles_on_processed=False):
    processed = image.copy()
    vis = image.copy()

    edges = cv2.Canny(processed, 150, 250, L2gradient=True, apertureSize=3)

    # This copying process extends the image boundaries by max_circle_radius
    # So that cans on the image border might be detected
    # Since houghCircles usually only likes circles inside of the image
    extendedWidth = edges.shape[0] + 2*max_circle_radius
    extendedHeight = edges.shape[1] + 2*max_circle_radius
    processed = np.zeros((extendedWidth, extendedHeight), np.uint8)
    processed[max_circle_radius:max_circle_radius + edges.shape[0],
              max_circle_radius:max_circle_radius + edges.shape[1]] = edges

    kernel = np.ones((3, 3), dtype="uint8")
    processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel)

    circles = cv2.HoughCircles(
        processed, method=cv2.HOUGH_GRADIENT, dp=3, minDist=45,
        param1=250, param2=200, minRadius=45, maxRadius=max_circle_radius)

    processed = gray_to_RGB(processed)
    if (draw_circles_on_processed):
        processed = draw_circles(processed, circles)
    circles = remove_border_from_circles(processed, circles, border=max_circle_radius)

    return processed, circles

# 2.3 remove_border_from_circles()
# For each circle, check how many of the pixels on it's outer boundary are actually white.
# If less than min_ratio are white, discard this circle.


def remove_border_from_circles(image, circles, border, min_ratio=0.2):
    filtered_circles = []
    circled = image.copy()
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")

        for (x, y, r) in circles:
            filtered_circles += [[x-border, y-border, r]]
    return np.array([filtered_circles])


def bottle_detection( image, number_of_octaves=4 ):
    processed = image.copy()

    octaves = [ cv2.resize( processed, dsize=(0, 0), fx=1/float(x), fy=1/float(x), interpolation=cv2.INTER_LINEAR ) for x in range(1, number_of_octaves+1) ]
    octaves = map( lambda img: cv2.GaussianBlur(img, (5, 5), 0, 0), octaves )
    octaves = map( lambda img: cv2.Canny(img, 150, 250, L2gradient=True, apertureSize=3), octaves )
    
    octave_circles = map( lambda i: cv2.HoughCircles(
        octaves[i], method=cv2.HOUGH_GRADIENT, dp=2.8, minDist=45/(i+1), param1=250, param2=180/(i+1), minRadius=30/(i+1), maxRadius=60/(i+1)),
        range(number_of_octaves) )

    octaves = map( lambda img: gray_to_RGB(img), octaves)

    circles = merge_octave_circles( octave_circles )
    circles = filter_octave_circles( circles )


    return processed, circles

def merge_octave_circles(octave_circles):
    merged_circles = []
    for i in range(len(octave_circles)):
        if octave_circles[i] is not None:
            for (x, y, r) in octave_circles[i][0]:
                merged_circles += [[x*(i+1), y*(i+1), r*(i+1)]]

    return np.array([merged_circles])

def filter_octave_circles( circles, identical_radius=0.3 ):
    filtered_circles = None
    if circles is not None:
        filtered_circles = []
        circles = np.round(circles[0, :]).astype("int")
        identical_candidates = find_identical_candidates(circles, identical_radius)

        identical_candidates_by_length = map( lambda (k, v): (k, len(v)), identical_candidates.iteritems())
        identical_candidates_by_length = sorted( identical_candidates_by_length, key=lambda circle: circle[1], reverse=True )

        circles_not_yet_clustered = map( lambda (k, v): k, identical_candidates.iteritems())
        for circle in identical_candidates_by_length:
            if (circle[0] in circles_not_yet_clustered):
                filtered_circles += [(circle[0])]
                for identical in identical_candidates[circle[0]]:
                    circles_not_yet_clustered = [icircle for icircle in circles_not_yet_clustered if icircle != identical]
                    
    return np.array([filtered_circles])

def find_identical_candidates( circles, identical_radius ):
    identical_candidates = {}
    for (x, y, r) in circles:
        identical_candidates[(x, y, r)] = []
        for (nx, ny, nr) in circles:
            distance_of_centers = math.sqrt((x-nx)**2 + (y-ny)**2)
            if ( 0 < distance_of_centers < r*identical_radius ):
                identical_candidates[(x, y, r)] += [(nx, ny, nr)]

    return identical_candidates


#
#
#
#
#
#
#
#
#


class Real_World_Locator(object):

    map_folder = "location_new/"
    upper_shelf_height = 24.5
    lower_shelf_height = 12.5

    def __init__(self, shelf, camera):
        self.shelf = shelf
        self.camera = camera

        self.upper_shelf_image_points = None
        self.lower_shelf_image_points = None

        self.world_points = None

        self.init_maps()


    def init_maps(self):
        upper_shelf_path = self.map_folder + self.shelf + "_" + str(self.upper_shelf_height) + "_" + str(self.camera) + ".png"
        lower_shelf_path = self.map_folder + self.shelf + "_" + str(self.lower_shelf_height) + "_" + str(self.camera) + ".png"
        
        upper_shelf_image = read_image( upper_shelf_path )
        lower_shelf_image = read_image( lower_shelf_path )

        self.upper_shelf_image_points = self.init_map_points( upper_shelf_image )
        self.lower_shelf_image_points = self.init_map_points( lower_shelf_image )

        self.init_world_points( upper_shelf_image )

    def init_map_points(self, location_map):
      width, height, channels = location_map.shape
      assert channels == 4, "Your location map doesn't have transparency. That sounds wrong"
      flattened_image = np.ones((width, height, 3), np.uint8)
      flattened_image = flattened_image * 255
      flattened_image = paste_transparent(flattened_image, location_map)

      detector = cv2.SimpleBlobDetector_create()
      keypoints = detector.detect(flattened_image)

      if ( len(keypoints) is not 2):
        raise Value_Error("When initializing location maps, an incorrect number of keypoints has been found. There should be only two.")

      top_left_pixel = keypoints[0].pt if keypoints[0].pt[0] < keypoints[1].pt[0] else keypoints[1].pt
      bottom_right_pixel = keypoints[1].pt if keypoints[0].pt[0] < keypoints[1].pt[0] else keypoints[0].pt

      top_left_pixel = (int(top_left_pixel[0]) , int(top_left_pixel[1]))
      bottom_right_pixel = (int(bottom_right_pixel[0]), int(bottom_right_pixel[1]))

      print 'top_left_pixel',top_left_pixel
      print 'bottom_right_pixel',bottom_right_pixel

      return (top_left_pixel, bottom_right_pixel)

    '''
    def init_map_points(self, location_map, scale=15):
        distortion_points = []
        distortion_points_dict = {}
        distortion_point_locations = get_distortion_points(location_map)

        for point in distortion_point_locations:
            distortion_points += [Distortion_Point(point[1], point[0], location_map)]

        for point in distortion_points:
            distortion_points_dict[(point.real_coords_x, point.real_coords_y)] = point

        min_real_x = min(map(lambda x: x[0], distortion_points_dict.keys()))
        max_real_x = max(map(lambda x: x[0], distortion_points_dict.keys()))
        min_real_y = min(map(lambda x: x[1], distortion_points_dict.keys()))
        max_real_y = max(map(lambda x: x[1], distortion_points_dict.keys()))

        top_left_pixel_x = 10 * scale
        top_left_pixel_y = 10 * scale
        bottom_right_pixel_x = (max_real_x-10-min_real_x)*scale
        bottom_right_pixel_y = (max_real_y-10-min_real_y)*scale

        print 'top_left_pixel_x'    , top_left_pixel_x    , 'top_left_pixel_y'    , top_left_pixel_y
        print 'bottom_right_pixel_x', bottom_right_pixel_x, 'bottom_right_pixel_y', bottom_right_pixel_y

        return ((top_left_pixel_x,top_left_pixel_y), (bottom_right_pixel_x,bottom_right_pixel_y))
    '''

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

