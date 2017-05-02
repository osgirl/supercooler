# supercooler
Fresh codebase for second prototype for AB-InBev

installation:
to move from local repo to remote computers:

from within the supercooler directory:
scp -rp ./scripts pi@192.168.1.*:scripts

then ssh to the remote computer

cd scripts
sudo chmod 777 *
sudo ./install_requirements.sh


copy settings.py to remote computer
scp -p settings.py pi@192.168.1.*:~/scripts/supercooler

post-install cleanup:
mv ~/scripts/supercooler ~/supercooler
mv ~/scripts/thirtybirds-2.0 ~/thirtybirds_2_0 






