echo
echo "MOVE AND ADJUST RC.LOCAL PERMISSIONS"
echo

sudo cp /home/pi/supercooler/scripts/rc.local /etc/rc.local
sudo chmod 755 /etc/rc.local

exit 0