import time, sys, json, requests
from random import randint, uniform

from product_names import products

# test ec2 instance
endpoint = "http://ec2-54-175-77-220.compute-1.amazonaws.com/update"

# test local
# endpoint = "http://127.0.0.1:9000/update"

def main():

    data = []
    upload_items = True
    number_items = 25

    if len(sys.argv) > 1:
        number_items = int(sys.argv[1])
    if len(sys.argv) > 2:
        upload_items = ''

    shelfs = ['A','B','C','D']
    for item in range(0,number_items):
        data.append({
            'type': randint(1,len(products)),
            'shelf': shelfs[randint(0,3)],
            'x': uniform(20,565-20),
            'y': uniform(20,492-20)
        });

    package = {'upload': upload_items, 'timestamp':int(time.time()), 'data':json.dumps(data)}

    try:
        response = requests.get(endpoint, params=package)
        print('response: {} - {}'.format(response.text, response.status_code))
    except requests.exceptions.RequestException as e:
        print('error: {}',format(e))
        sys.exit(1)

if __name__ == '__main__':
    main()
