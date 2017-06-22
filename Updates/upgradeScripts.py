scripts = {
    "0.00":[
        "echo \"no new upgrade scripts yet\"",
    ],
    "0.01":[
        "cp /home/pi/supercooler/scripts/rc.local /etc/rc.local",
    ],
    "0.02":[
        "cp /home/pi/supercooler/scripts/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf",
    ],
    "0.03":[
    	"sudo dpkg -i /home/pi/supercooler/packages/opencv_3.2.0-1_armhf.deb",
    ],
    "0.05":[
        "sudo cp /home/pi/supercooler/scripts/rc.local /etc/rc.local",
        "sudo chmod 755 /etc/rc.local",
    ]
}
