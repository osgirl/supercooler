"""

"""
import time
import threading
import settings
import yaml
import json
import subprocess
import base64

from thirtybirds_2_0.Network.manager import init as network_init

from web_interface import WebInterface

# use wiringpi for software PWM
import wiringpi as wpi

class Door(threading.Thread):
    def __init__(self, door_close_event_callback, door_open_event_callback):
        threading.Thread.__init__(self)
        self.closed = True
        self.door_pin_number = 29
        self.last_closure = time.time()
        self.estmated_inventory_duration = 60
        self.door_close_event_callback = door_close_event_callback
        self.door_open_event_callback = door_open_event_callback
        # use pin 29 as door sensor (active LOW)
        wpi.pinMode(self.door_pin_number, wpi.INPUT)
        wpi.pullUpDnControl(self.door_pin_number, wpi.PUD_UP)

    def run(self):
        while True:
            closed_temp =  not wpi.digitalRead(self.door_pin_number)
            if self.closed != closed_temp:
                print "Door.run self.closed=", self.closed
                self.closed = closed_temp
                if self.closed:
                    self.door_close_event_callback(True if self.last_closure + self.estmated_inventory_duration <= time.time() else False)
                else: 
                    self.door_open_event_callback()
            time.sleep(0.5)

class Lights():
    def __init__(self):
        self.pwm_pins = [21, 22, 23, 24]
        self.light_sequence_levels = [ 100, 50, 0]
        for pwm_pin in self.pwm_pins:
            wpi.pinMode(pwm_pin, wpi.OUTPUT)
            wpi.softPwmCreate(pwm_pin, 0, 100)

    def set_level_shelf(self, id, value):
        wpi.softPwmWrite(self.pwm_pins[id], value)

    def set_level_all(self, value):
        for shelf_id in range(4):
            self.set_level_shelf(shelf_id, value)

    def play_sequence_step(self, step):
        self.set_level_all(self.light_sequence_levels[step])

    def play_test_sequence(self):
        for j in xrange(-100, 101):
            for i in xrange(4): self.set_level_shelf(i, 100 - abs(j))
            wpi.delay(10)

    def all_off(self):
        for i in xrange(4): self.set_level_shelf(i, 0) # turn off the lights

class Camera_Units():
    def __init__(self, network):
            self.network = network
    def capture_image(self, light_level_sequence_position):
        self.network.send("capture_image", light_level_sequence_position)
    def process_images_and_report(self):
        self.network.send("process_images_and_report", "")
    def send_update_command(self, cool=False, birds=False, update=False, upgrade=False):
        self.network.send("remote_update", [cool, birds, update, upgrade])
    def send_update_scripts_command(self):
        self.network.send("remote_update_scripts", "")
    def send_reboot(self):
        self.network.send("reboot")
    #def ping_nodes_go(self):
    #   self.network.send("say_hello_to_node")

class Main(): # rules them all
    def __init__(self, network):
        self.network = network
        self.web_interface = WebInterface()
        self.lights = Lights()
        self.door = Door(self.door_close_event_handler, self.door_open_event_handler)
        self.door.daemon = True
        self.door.start()
        self.camera_units = Camera_Units(self.network)
        self.camera_capture_delay = 3

    def door_open_event_handler(self):
        print "Main.door_open_event_handler"
        self.web_interface.send_door_open()

    def door_close_event_handler(self, start_inventory):
        print "Main.door_close_event_handler , start_inventory= ", start_inventory
        self.web_interface.send_door_close()
        if not start_inventory: 
            return
        for light_level_sequence_position in range(3):
            self.lights.play_sequence_step(light_level_sequence_position)
            self.camera_units.capture_image(light_level_sequence_position)
            time.sleep(self.camera_capture_delay)
        self.lights.all_off()
        self.camera_units.process_images_and_report()

def network_status_handler(msg):
    print "network_status_handler", msg

def network_message_handler(msg):
    try:
        print "network_message_handler", msg
        topic = msg[0]
        #print "topic", topic
        if topic == "__heartbeat__":
            print "heartbeat received", msg
        """
        if topic == "found_beer":
            if msg[1] != "":

                data = msg[1]
                print "found_beer: got %d bytes" % (len(data))

                with open("/home/pi/supercooler/Captures/Capture.png", "wb") as f:
                    f.write(base64.b64decode(data))
                    print "saved capture"
            else:
                print "found_beer: empty message"
        """
        if topic == "update_complete":
            print 'update complete for host: ', msg[1]

    except Exception as e:
        print "exception in network_message_handler", e

def init(HOSTNAME):
    # setup LED control and door sensor
    #io_init()
    wpi.wiringPiSetup()
    # global network
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
    main = Main(network)


