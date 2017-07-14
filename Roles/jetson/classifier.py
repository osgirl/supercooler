import sys
import tensorflow as tf
import os
import time
import subprocess
import cv2

class Classifier():

    def __init__(self):

        self.label_lookup = {
            "bottlebecks"               : 1,
            "bottlebudamerica"          : 2,
            "bottlebudlight"            : 3,
            "bottleplatinum"            : 4,
            "bottlecorona"              : 5,
            "bottlehoegaarden"          : 6,
            "bottleultra"               : 7,
            "bottleshocktopraspberry"   : 8,
            "bottleshocktoppretzel"     : 9,
            "bottlestella"              : 107,
            "canbudamerica"             : 11,
            "canbudlight"               : 12,
            "canbusch"                  : 13,
            "canbusch"                  : 14,
            "cannaturallight"           : 15,
            "canbudamerica"             : 16,
            "canbudice"                 : 17,
            "canbudlight"               : 18
        }

        self.product_specific_confidence_thresholds = {
            "bottlebecks"               : 0.99,
            "bottlebudamerica"          : 0.99,
            "bottlebudlight"            : 0.99,
            "bottleplatinum"            : 0.99,
            "bottlecorona"              : 0.95,
            "bottlehoegaarden"          : 0.99,
            "bottleultra"               : 0.98,
            "bottleshocktopraspberry"   : 0.99,
            "bottleshocktoppretzel"     : 0.98,
            "bottlestella"              : 0.99,
            "canbudamerica"             : 0.95,
            "canbudlight"               : 0.99,
            "canbusch"                  : 0.94,
            "cannaturallight"           : 0.95,
            "canbudamerica"             : 0.99,
            "canbudice"                 : 0.99,
            "canbudlight"               : 0.99
        }

        # Loads label file, strips off carriage return
        self.label_lines = [line.rstrip() for line 
                           in tf.gfile.GFile("/home/nvidia/supercooler/Roles/jetson/tf_files/retrained_labels.txt")]

    # def guess_images(self, input_dir):
    #     input_images = sorted([f for f in os.listdir(input_dir) if f.endswith(".jpg")])
    #     with tf.Session() as sess:
    #         return [(i, guess_image(sess, i)) for i in input_images]

    def guess_image(self, tf_session, image):
        # Feed the image_data as input to the graph and get first prediction
        softmax_tensor = tf_session.graph.get_tensor_by_name('final_result:0')
        
        print "run tf session..."
        predictions = tf_session.run(softmax_tensor, \
                 {'DecodeJpeg/contents:0': image})
        
        # Sort to show labels of first prediction in order of confidence
        print "sort labels.."
        top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]

        scores = [(self.label_lines[node_id], predictions[0][node_id]) for node_id in top_k]

        # throttle to prevent overheating
        '''while get_temp_celcius() > 55:
            print "it's hot!", get_temp_celcius()
            time.sleep(1)'''
        
        return scores

def classify_images(potential_objects, image, threshold=0.6):

    # if the best guess falls below this threshold, assume no match
    confidence_threshold = threshold

    print "Classifier.classify_images"

    # start tensorflow session, necessary to run classifier
    classifier = Classifier()
    with tf.Session() as sess:

        for i, candidate in enumerate(potential_objects):

            # report progress every ten images
            if (i%10) == 0:
                print 'processing %dth image' % i
                time.sleep(1)

            # crop image and encode as jpeg (classifier expects jpeg)
            print "cropping..."

            r  = candidate['radius']
            (img_height, img_width) = image.shape[:2]

            x1 = max(candidate['shelf_x']-r, 0)
            y1 = max(candidate['shelf_y']-r, 0)
            x2 = min(x1 + r*2, img_width )
            y2 = min(y1 + r*2, img_height)

            img_crop = image[y1:y2, x1:x2]
            img_jpg = cv2.imencode('.jpg', img_crop)[1].tobytes()

            print "cropped image, w,h = ", x2-x1, y2-y1

            # get a list of guesses w/ confidence in this format:
            # guesses = [(best guess, confidence), (next guess, confidence), ...]
            print "running classifier..."

            guesses = classifier.guess_image(sess, img_jpg)
            best_guess, confidence = guesses[0]

            # print result from classifier
            print guesses


#XXX moved this from guess_images.. is that ok?
# Unpersists graph from file
with tf.gfile.FastGFile("/home/nvidia/supercooler/Roles/jetson/tf_files/retrained_graph.pb", 'rb') as f:
    graph_def = tf.GraphDef()
    graph_def.ParseFromString(f.read())
    _ = tf.import_graph_def(graph_def, name='')
