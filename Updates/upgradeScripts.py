scripts = {
    "0.00":[
        "echo \"no new upgrade scripts yet\"",
    ],
    "0.05":[
        "sudo cp /home/pi/supercooler/scripts/rc.local /etc/rc.local",
        "sudo chmod 755 /etc/rc.local",
    ],
    "0.08":[
        "apt-get install -y build-essential libssl-dev libffi-dev",
        "sudo pip install --upgrade watson-developer-cloud",
        "sudo apt-get install -y zip"
    ]
}

