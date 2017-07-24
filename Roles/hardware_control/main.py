import os
import time
import threading
import settings
import subprocess
import wiringpi as wpi

from thirtybirds_2_0.Network.manager import init as network_init
from thirtybirds_2_0.Updates.manager import init as updates_init

########################
## UTILS
########################

class Utils(object):
    def __init__(self, hostname):
        self.hostname = hostname
    def reboot(self):
        os.system("sudo reboot now")

    def get_shelf_id(self):
        return self.hostname[11:][:1]

    def get_camera_id(self):
        return self.hostname[12:]

    def create_image_file_name(self, timestamp, light_level, process_type):
        return "{}_{}_{}_{}_{}.png".format(timestamp, self.get_shelf_id() ,  self.get_camera_id(), light_level, process_type) 

    def remote_update_git(self, supercooler, thirtybirds, update, upgrade):
        if supercooler:
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/supercooler')
        if thirtybirds:
            subprocess.call(['sudo', 'git', 'pull'], cwd='/home/pi/thirtybirds_2_0')
        return 

    def remote_update_scripts(self):
        updates_init("/home/pi/supercooler", False, True)
        return

    def get_update_script_version(self):
        (updates, ghStatus, bsStatus) = updates_init("/home/pi/supercooler", False, False)
        return updates.read_version_pickle()

    def get_git_timestamp(self):
        return commands.getstatusoutput("cd /home/pi/supercooler/; git log -1 --format=%cd")[1]   

    def get_client_status(self):
        return (self.hostname, self.get_update_script_version(), self.get_git_timestamp())



class Door(threading.Thread):
    def __init__(self, door_close_event_callback, door_open_event_callback):
        threading.Thread.__init__(self)
        self.closed = True
        self.door_pin_number = 25
        self.last_closure = time.time()
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
                    self.door_close_event_callback()
                else: 
                    self.door_open_event_callback()
            time.sleep(0.5)

class Lights():
    def __init__(self):
        self.pwm_pins = [21, 22, 23, 24]
        self.light_sequence_levels = [ 10, 5, 0]

        # setup pins for software PWM via wiringpi
        for pwm_pin in self.pwm_pins:
            wpi.pinMode(pwm_pin, wpi.OUTPUT)
            wpi.softPwmCreate(pwm_pin, 0, 10)

    # set light level on a specific shelf    
    def set_level_shelf(self, id, value):
        wpi.softPwmWrite(self.pwm_pins[id], value)

    # set all shelves to the same specified light level
    def set_level_all(self, value):
        for shelf_id in range(4):
            self.set_level_shelf(shelf_id, value)

    # set lights to predefined sequence step
    def play_sequence_step(self, step):
        self.set_level_all(self.light_sequence_levels[step])

    def play_test_sequence(self):
        for j in xrange(-10, 11):
            for i in xrange(4): self.set_level_shelf(i, 10 - abs(j))
            wpi.delay(200)

    # turn off the lights
    def all_off(self):
        for i in xrange(4): self.set_level_shelf(i, 0)


class Main(): # rules them all
    def __init__(self, network):
        self.network = network

        self.lights = Lights()

        self.door = Door(self.door_close_event_handler, self.door_open_event_handler)
        self.door.daemon = True
        self.door.start()
        self.last_closure = time.time()

    def door_close_event_handler(self):
        network.send("door_closed", "")

    def door_open_event_handler(self):
        network.send("door_opened", "")


def network_status_handler(msg):
    print "network_status_handler", msg


def network_message_handler(msg):
    print "network_message_handler", msg
    topic = msg[0]
    data = msg[1]
    #host, sensor, data = yaml.safe_load(msg[1])
    if topic == "__heartbeat__":
        print "heartbeat received", msg
    elif topic == "reboot":
        os.system("sudo reboot now")
  
    elif topic == "set_light_level":
        print "set light level", data
        lights = main.lights.set_level_all(eval(data))

    elif topic == "reboot":
        utils.reboot()

    elif topic == "client_monitor_request":
        network.send("client_monitor_response", utils.get_client_status())
    #elif topic == "client_monitor_request":
    #    network.send("client_monitor_response", main.thirtybirds_client_monitor_client.send_client_status())
    
    else: # [ "capture_image" ]
        main.add_to_queue(topic, data)
        

def init(HOSTNAME):
    global main
    global network
    global utils

    wpi.wiringPiSetup()

    network = network_init(
        hostname=HOSTNAME,
        role="client",
        discovery_multicastGroup=settings.discovery_multicastGroup,
        discovery_multicastPort=settings.discovery_multicastPort,
        discovery_responsePort=settings.discovery_responsePort,
        pubsub_pubPort=settings.pubsub_pubPort,
        message_callback=network_message_handler,
        status_callback=network_status_handler
    )

    utils = Utils(HOSTNAME)

    main = Main(network)
    #main.daemon = True
    #main.start()

    # TODO: clean this up
    # initialize shelf power control
    wpi.pinMode(27, wpi.OUTPUT)
    wpi.pinMode(28, wpi.OUTPUT)
    wpi.pinMode(29, wpi.OUTPUT)
    wpi.digitalWrite(27, 1)
    wpi.digitalWrite(28, 1)
    wpi.digitalWrite(29, 1)

    network.subscribe_to_topic("system")  # subscribe to all system messages
    network.subscribe_to_topic("set_light_level")
    network.subscribe_to_topic("client_monitor_request")
    network.subscribe_to_topic("reboot")

    #network.subscribe_to_topic("client_monitor_request")

    return main
