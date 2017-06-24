import time
import json

import requests
from random import randint, uniform

from web_endpoints import web_endpoint

class WebInterface:
    # make sure web_endpoints.py is in the ./Roles/conductor on the raspberry pi
    endpoint = web_endpoint

    def __upload_data(self, route, data):
        print "go go"
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
        print "ayo"
        try:
            data = json.dumps(data)
            print data
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
