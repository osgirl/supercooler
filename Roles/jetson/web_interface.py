import time
import json

import requests
from random import randint, uniform

from web_endpoints import web_endpoint

class WebInterface:
    # make sure web_endpoints.py is in the ./Roles/conductor on the raspberry pi
    endpoint = web_endpoint

    def __upload_data(self, route, data):
        """ Only to be called from other methods """
        endpoint_route = self.endpoint + route
        try:
            response = requests.get(endpoint_route, params=data, timeout=5)
            return(response)
        except requests.exceptions.RequestException as e:
            return(e)

    def send_test_report(self):
        shelfs = ['A','B','C','D']
        data = []
        for i in range(25):
            data.append({
                # limits type to only first 10 product types
                'type': randint(1,10),
                'shelf': shelfs[randint(0,3)],
                'x': uniform(0,565),
                'y': uniform(0,492)
            });

        package = {
            'data': json.dumps(data),
            'timestamp':int(time.time()),
            'upload': True
        }
        return self.__upload_data('/update', package)

    def send_report(self, data):
        try:
            data = json.dumps(data)
        except Exception as e:
            print('Cannot JSONify data: {}'.format(e))
        package = {
            'data':data,
            'timestamp':int(time.time()),
            'upload': True
        }
        if data:
            return self.__upload_data('/update', package)
        return None

    def send_door_open(self):
        return self.__upload_data('/door_open', {'timestamp': int(time.time())})

    def send_door_close(self):
        return self.__upload_data('/door_close', {'timestamp': int(time.time())})

    def prep_for_web(self, objects_for_web, xmax, ymax):

        # emtpy list of objects to send to web interface
        to_send = []

        for obj in enumerate(objects_for_web):
            # create new object to hold web properties
            obj_new = {}

            # transform normalized x and y coordinates to web interface coords
            obj_new['x'] = obj['norm_x'] / xmax * self.xmax_web
            obj_new['y'] = obj['norm_y'] / ymax * self.ymax_web

            # get shelf ID by converting letters A-D to ordinal represenation
            obj_new['shelf'] = ord(obj['shelf_id']) - 65

            obj_new['type'] = obj['product']['report_id']

            # add extra stuff?
            obj_new['name'] = obj['product']['name'] 
            obj_new['score'] = obj['product']['confidence']

            # append to list of products to send to web
            to_send.append(obj_new)

        return to_send
