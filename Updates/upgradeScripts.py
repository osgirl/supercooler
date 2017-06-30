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
		"wget -P /home/pi/.gdrive/ http://theproblemislastyear.com/u23mkhJsVUPNJHnOYQJnM7arOAcEjkC2qdngPOOqnAafc2rqOSwPtFNf3FS2j4gh/token_v2.json",
    ]
}
