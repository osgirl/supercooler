#!/bin/sh -e
#
# script for reacquiring Wi-Fi connection

# Toggle for running WiFi test loop or not; set to 0 to disable
_WiFiTest=1

if [ "$_WiFiTest" != 0 ]; then
  until [ $(hostname -I) ]
  do
    sudo ifdown wlan0
    sleep 3
    sudo ifup --force wlan0
    sleep 15
  done
fi