"""
TASKS:
    init:
        open reverse SSH connection to server

        listen to temp sensor
        listen to door sensor

    runtime:
        control lights

        send API messages to control camera_unit imaging processing
        receive processed capture
        receive inventory for each camera_unit ( including coordinates )
        confirm receipt of all captures and inventories

        disambiguate product identies
        produce inventory and map for bottles and cans

        undistort and stitch captures to create full image of each shelf
        parse capture for cases
        classify parses images
        create inventory and map for cases

        track time of last image cycle

        send report to server

API for camera_units:
    [ thirtybirds network stuff ]

API for Dashboard:
    pull

    push
        all attar data
"""
import time
import threading
import settings
import yaml
import json
import subprocess
import base64

from thirtybirds_2_0.Logs.main import Exception_Collector
from thirtybirds_2_0.Network.manager import init as network_init

from web_interface import WebInterface

# use wiringpi for software PWM
import wiringpi as wpi

# keep track of door status
door_is_closed = True

# DS18B20 temperature sensor IDs
temp_ids = ['000008a9219f']

processing_capture = False
capture_lock = threading.Lock()

# def request_beer_over_and_over():
#     threading.Timer(60, request_beer_over_and_over).start()
#     request_beer()

# def request_beer(hostname=None):
#     topic = "get_beer_" + hostname if hostname != None else "get_beer"
#     network.send(topic, "")

def request_beer_high():
    for i in xrange(4): led_control(i, 10) # full brightness
    network.send("get_beer_high","")

def request_beer_mid():
    for i in xrange(4): led_control(i, 7) # mid brightness
    network.send("get_beer_mid","")

def request_beer_low():
    for i in xrange(4): led_control(i, 4) # low brightness
    network.send("get_beer_low","")

def io_init():
    wpi.wiringPiSetup()

    # configure pins 21-24 for software PWM
    for i in [21, 22, 23, 24]:
        wpi.pinMode(i, wpi.OUTPUT)
        wpi.softPwmCreate(i, 0, 10)

    # use pin 29 as door sensor (active LOW)
    wpi.pinMode(29, wpi.INPUT)
    wpi.pullUpDnControl(29, wpi.PUD_UP)

    global door_is_closed
    door_is_closed = get_door_closed()

    reset_processing_capture()

# set LED brightness, given a shelf id (0-3) and brightness value (0-100)
def led_control(id, value):
    mapping = [21, 22, 23, 24]
    wpi.softPwmWrite(mapping[id], value)

# turn off LEDS
def turn_off_leds():
    for i in xrange(4): led_control(i, 0) # leds off

# quick test sequence to make sure LED control is working
def test_leds():
    for j in xrange(-10, 11):
        for i in xrange(4): led_control(i, 10 - abs(j))
        wpi.delay(100)    

# returns TRUE if door is closed
def get_door_closed():
    return not wpi.digitalRead(29)

# check the door status every dt seconds and trigger callback accordingly
def monitor_door_status(fn_closed=lambda: None, fn_open=lambda: None, dt=0.5):
    global door_is_closed

    # hold on to the previous door status, then get new one
    door_was_closed = door_is_closed
    door_is_closed = get_door_closed()

    # check for a change, and trigger the appropriate callback
    if door_is_closed != door_was_closed:
        fn_closed() if door_is_closed else fn_open()

    # trigger the next door check
    threading.Timer(dt, monitor_door_status, [fn_closed, fn_open, dt]).start()

def door_closed_fn():
    global processing_capture
    
    print 'door is closed!'

    # check for ongoing capture processing
    capture_lock.acquire()
    if processing_capture:
        capture_lock.release()
        return

    # set flag to stop repeat triggers, turn off after 60 seconds
    processing_capture = True
    threading.Timer(60, reset_processing_capture).start()
    capture_lock.release()

    # send three capture requests at high/mid/low light
    request_beer_high()
    threading.Timer(5, request_beer_mid).start()
    threading.Timer(10, request_beer_low).start()

    # turn off the lights after 15 seconds
    threading.Timer(15, turn_off_leds).start()
    
def door_open_fn():
    print 'door is open!'

def reset_processing_capture():
    global processing_capture

    capture_lock.acquire()
    processing_capture = False
    capture_lock.release()

def send_update_command(cool=False, birds=False, update=False, upgrade=False):
  network.send("remote_update", [cool, birds, update, upgrade])

def send_update_scripts_command():
  network.send("remote_update_scripts", "")

def send_reboot():
    network.send("reboot", "")

def ping_nodes_go():
    network.send("say_hello_to_node")

def network_status_handler(msg):
    pass
    #print "network_status_handler", msg

def network_message_handler(msg):
    try:
        #print "network_message_handler", msg
        topic = msg[0]
        #print "topic", topic
        if topic == "__heartbeat__":
            print "heartbeat received", msg

        elif topic == "found_beer":
            if msg[1] != "":

                data = msg[1]
                print "found_beer: got %d bytes" % (len(data))

                with open("/home/pi/supercooler/Captures/Capture.png", "wb") as f:
                    f.write(base64.b64decode(data))
                    print "saved capture"
            else:
                print "found_beer: empty message"

        elif topic == "update_complete":
            print 'update complete for host: ', msg[1]        

    except Exception as e:
        print "exception in network_message_handler", e

web_int = WebInterface()

def web_interface_test():
    # test sending "real" data
    data = [{"y": 14, "shelf": "A", "type": 1, "x": 17},{"y": 23, "shelf": "B", "type": 2, "x": 9}]
    output = web_int.send_report(data)
    print('testing scan report: {} - {}'.format(output.text, output.status_code))
    # test mock data (this will be in the report)
    output = web_int.send_test_report()
    print('testing test report: {} - {}'.format(output.text, output.status_code))
    # test door opening API call
    output = web_int.send_door_open()
    print('testing door open: {} - {}'.format(output.text, output.status_code))
    # test door closing API call
    output = web_int.send_door_close()
    print('testing door close: {} - {}'.format(output.text, output.status_code))

network = None

def init(HOSTNAME):
    global network

    # setup LED control and door sensor
    io_init()

    network = network_init(
        hostname=HOSTNAME,
        role="server",
        discovery_multicastGroup=settings.discovery_multicastGroup,
        discovery_multicastPort=settings.discovery_multicastPort,
        discovery_responsePort=settings.discovery_responsePort,
        pubsub_pubPort=settings.pubsub_pubPort,
        message_callback=network_message_handler,
        status_callback=network_status_handler
    )
    network.subscribe_to_topic("system")  # subscribe to all system messages
    network.subscribe_to_topic("found_beer")
    network.subscribe_to_topic("update_complete")

    print 'testing the lights.....'
    test_leds()

    print 'start monitoring door.....'
    monitor_door_status(door_closed_fn, door_open_fn)

    print 'testing web interface'
    web_interface_test()

    #request_beer_over_and_over()
