import sys
import tensorflow as tf
import os
import time
import subprocess
import cv2

# def guess_images(self, input_dir):
#     input_images = sorted([f for f in os.listdir(input_dir) if f.endswith(".jpg")])
#     with tf.Session() as sess:
#         return [(i, guess_image(sess, i)) for i in input_images]

def guess_image(tf_session, image, label_lines):
    # Feed the image_data as input to the graph and get first prediction
    softmax_tensor = tf_session.graph.get_tensor_by_name('final_result:0')
    
    print "run tf session..."
    predictions = tf_session.run(softmax_tensor, \
             {'DecodeJpeg/contents:0': image})
    
    # Sort to show labels of first prediction in order of confidence
    print "sort labels.."
    top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]

    scores = [(label_lines[node_id], predictions[0][node_id]) for node_id in top_k]

    # throttle to prevent overheating
    '''while get_temp_celcius() > 55:
        print "it's hot!", get_temp_celcius()
        time.sleep(1)'''
    
    return scores

def classify_images(potential_objects, image, sess, label_lines, threshold=0.6):

    # if the best guess falls below this threshold, assume no match
    confidence_threshold = threshold

    print "Classifier.classify_images"

    # start tensorflow session, necessary to run classifier
    #classifier = Classifier()
    
    #with tf.Session() as sess:
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

        guesses = guess_image(sess, img_jpg, label_lines)
        best_guess, confidence = guesses[0]

        # print result from classifier
        print guesses
