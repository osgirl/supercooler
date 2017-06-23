scripts = {
    "0.00":[
        "echo \"no new upgrade scripts yet\"",
    ],
    "0.05":[
        "sudo cp /home/pi/supercooler/scripts/rc.local /etc/rc.local",
        "sudo chmod 755 /etc/rc.local",
    ],
    "0.06":[
        "sudo cp scripts/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf",
    ]
}
