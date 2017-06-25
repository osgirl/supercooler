import cv2
import numpy as np

class Image_Parser():
    def __init__(self, hostname, network, min_size=65):
        self.hostname = hostname
        self.network = network
        self.min_size = min_size
        self.distortion = np.array([[-6.0e-5, 0.0, 0.0, 0.0]], np.float64)
        self.max_confdence = 1.0
    
    def equalize_histogram(self, img):
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        equalized = clahe.apply(img)
        _, thresh = cv2.threshold(equalized, 0, 255, cv2.THRESH_TOZERO + cv2.THRESH_OTSU)
        return thresh

    def process_split(self, img):
        def process_channel(img):
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            equalized = clahe.apply(img)
            thresh = cv2.adaptiveThreshold(equalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 65, 17)
            opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, None)
            return opening

        b, g, r = map(process_channel, cv2.split(img))
        cv2.bitwise_and(b, g, b)
        processed = cv2.bitwise_and(b, r)
        processed = cv2.bilateralFilter(processed, 9, 100, 100)
        return processed

    def mask_blobs(self, gray):
        mask = np.zeros(gray.shape[:2], dtype='uint8')
        # detect blobs
        #mser = cv2.MSER_create(_delta=4, _min_area=65, _max_area=14400, _max_variation=1.0)
        #blobs, _ = mser.detectRegions(gray)
        mser = cv2.MSER_create(_delta=4, _min_area=65, _max_area=14400, _max_variation=1.0)
        blobs, _ = mser.detectRegions(gray)
        # find circular blobs
        for blob in blobs:
            hull = cv2.convexHull(blob.reshape(-1, 1, 2))
            epsilon = 0.01*cv2.arcLength(hull, True)
            poly = cv2.approxPolyDP(hull, epsilon, True)
            # select polygons with more than 9 vertices
            if len(poly) > 9: 
                cv2.polylines(mask, [blob], 1, 255, 1)
        return mask

    def calc_camera_matrix(self, (height,width)):
        cam = np.eye(3, dtype=np.float32) # assume unit matrix for camera
        cam[0, 2] = width  / 2.0  # center x
        cam[1, 2] = height / 2.0  # center y
        cam[0, 0] = 10.0          # focal length x
        cam[1, 1] = 10.0          # focal length y
        return cam

    def mask_beers(self, img, camera_matrix):
        # create masks to accumulate blobs detected by each pass
        mask_distorted = np.zeros(img.shape[:2], dtype = 'uint8')
        mask = np.zeros(img.shape[:2], dtype = 'uint8')
        # distorted:
        # CLAHE and Otsu threshold
        equalized = self.equalize_histogram(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        mask_distorted += self.mask_blobs(equalized)
        # adaptive threshold
        processed = self.process_split(img)
        mask_distorted += self.mask_blobs(processed)
        # undistorted:
        img_out = cv2.undistort(img, camera_matrix, self.distortion )
        # CLAHE and Otsu threshold
        equalized = self.equalize_histogram(cv2.cvtColor(img_out, cv2.COLOR_BGR2GRAY))
        mask += self.mask_blobs(equalized)
        # adaptive threshold
        processed = self.process_split(img_out)
        mask += self.mask_blobs  (processed)
        # undistort results from distorted image; sum with undistorted results
        mask += cv2.undistort(mask_distorted, camera_matrix, self.distortion )
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

            cv2.polylines(vis, [contour], 0, (0,0,255), 1)
            cv2.rectangle(vis, (x,y), (x+w,y+h), (0,255,0), 2)
            cv2.circle(vis, center, radius, (0,255,0), 2)                      
            cv2.putText(vis, '%.3f' % confidence, center, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,255), 2)
        #if self.interactive: plt.imshow(vis), plt.show()
        return (result, vis)

    def parse(self, img, img_50=None, img_0=None):
        img_weighted = img.copy()

        camera_matrix = self.calc_camera_matrix(img.shape[:2])
        print 'masking objects at light level 100'
        mask_final = self.mask_beers(img, camera_matrix)

        if img_50 is not None:
            print 'masking objects at light level 50'
            img_weighted = cv2.addWeighted(img_weighted, 0.5, img_50, 0.5, 0)
            mask_final += self.mask_beers(img_50, camera_matrix)
        if img_0  is not None:
            print 'masking objects at light level 0'
            img_weighted = cv2.addWeighted(img_weighted, 0.5, img_0 , 0.5, 0)
            mask_final += self.mask_beers(img_0 , camera_matrix)

        if img_50 is not None or img_0 is not None:
            print 'masking objects at average light level'
            mask_final += self.mask_beers(img_weighted, camera_matrix)

        img_out = cv2.undistort(img, camera_matrix, self.distortion)
        print 'picking masked objects'
        beer_bounds, vis = self.find_beers(mask_final, img_out.copy())

        return beer_bounds, vis, img_out
