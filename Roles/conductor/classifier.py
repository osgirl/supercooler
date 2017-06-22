import sys
import tensorflow as tf
import os
import time
import subprocess

class Classifier():

    def __init__(self):
        # Loads label file, strips off carriage return
        self.label_lines = [line.rstrip() for line 
                           in tf.gfile.GFile("tf_files/retrained_labels.txt")]

        #XXX moved this from guess_images.. is that ok?
        # Unpersists graph from file
        with tf.gfile.FastGFile("tf_files/retrained_graph.pb", 'rb') as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())
            _ = tf.import_graph_def(graph_def, name='')


    def guess_images(self, input_dir):
        input_images = sorted([f for f in os.listdir(input_dir) if f.endswith(".jpg")])
        with tf.Session() as sess:
            return [(i, guess_image(sess, i)) for i in input_images]

    def guess_image(self, tf_session, image_path):
        image_data = tf.gfile.FastGFile(image_path, 'rb').read()

        # Feed the image_data as input to the graph and get first prediction
        softmax_tensor = tf_session.graph.get_tensor_by_name('final_result:0')
        
        predictions = tf_session.run(softmax_tensor, \
                 {'DecodeJpeg/contents:0': image_data})
        
        # Sort to show labels of first prediction in order of confidence
        top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]

        scores = [(self.label_lines[node_id], predictions[0][node_id]) for node_id in top_k]

        # throttle to prevent overheating
        while get_temp_celcius() > 55:
            time.sleep(1)
        
        return scores

# get value from RPi onboard temp sensor, parse & convert to float
def get_temp_celcius():
    temp_cmd = '/opt/vc/bin/vcgencmd measure_temp'
    return float(subprocess.check_output(temp_cmd, shell=True)[5:9])
