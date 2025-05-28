# Fortigate - Iperf3 measurements
## Usage
### Invoke help
```
python --version
    Python 3.12.3
cd </wherever/this/project/is/stored>
apt install python3.11-venv
#### Rename Vars/input.yaml.orig to Vars/input.yaml and update the file
source env.sh
python main.py -h
usage: main.py [-h] -c CLIENT_LIST -o OUTPUT_FILE

    Runs iperf3 server on Linuxbox.
    Runs iperf3 client on Fortigate and store output to file.
    Operator to provide output file, final JSON values to be stored. Values in bits_per_second.
    Other Input values are defined in `Vars/input.yaml`.
    Fortigate Username and Password need to be exported before the script is run:
        export USER='supersecretuser'
        export PASSWORD='supersecretpassword'
    

options:
  -h, --help            show this help message and exit

Required arguments:
  -c CLIENT_LIST, --client-list CLIENT_LIST
                        Provide clients list filename. One IP per line.
  -o OUTPUT_FILE, --output-file OUTPUT_FILE
                        File to store the output JSON.

Thanks for using fortigate-iperf3 tool.
```
### Invoke manual script run
```
cd </wherever/this/project/is/stored>
source env.sh
export USER='supersecretuser'
export PASSWORD='supersecretpassword'
python main.py -c client_file -o output_file
```
### Invoke Cron script run
#### Once only
```
apt install pyenv
cat > /usr/sbin/danucem-sites-iperf3-speed-test.sh << EOF
\#\!\/bin\/bash
cd /root/fortigate-iperf3/
pyenv install 3.12.3 -y
pyenv local 3.12.3
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export USER='supersecretuser'
export PASSWORD='supersecretpassword'
python main.py -c client_file -o output_file
EOF
```
chmod 500 /usr/sbin/danucem-sites-iperf3-speed-test.sh
#### Install Cron job
```
crontab -e
0 0 1 * * /usr/sbin/danucem-sites-iperf3-speed-test.sh   # run script every night at 1 am
```
