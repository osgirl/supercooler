scripts = {
    "0.00":[
        "echo \"no new upgrade scripts yet\"",
    ],
    "0.05":[
        "sudo cp /home/pi/supercooler/scripts/rc.local /etc/rc.local",
        "sudo chmod 755 /etc/rc.local",
    ],
    "0.08":[
    	"sudo cp /home/pi/thirtybirds_2_0/Adaptors/Clouds/gdrive /home/pi/gdrive",
		"sudo chmod +x /home/pi/gdrive",
		"sudo install /home/pi/gdrive /usr/local/bin/gdrive",
		"mkdir /home/pi/.gdrive",
    ],
    "0.09":[
    	"{ sudo crontab -l; echo \"0 9 * * * /sbin/shutdown -r\"; } | sudo crontab -",
    ]
}
