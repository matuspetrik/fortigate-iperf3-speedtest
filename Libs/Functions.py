import os
import datetime
import sys
from time import sleep
import logging
from pyaml_env import parse_config, BaseConfig
from netbox import NetBox, status
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# import pprint


class Logger:

    def __init__(self, name=__name__, 
                 file_level=logging.DEBUG, console_level=logging.ERROR):
        """
        Initialize the logger.

        :param name: Logger name (usually __name__ of the module)
        :param log_file: Path to the log file
        :param file_level: Logging level for the file handler
        :param console_level: Logging level for the console handler
        :logger.error => print to stdout and file
        :logger.debug => print only to file
        """
        self.file_level = file_level
        self.console_level = console_level
        self.log_file='app.log'
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)  # Capture all levels; handlers filter further

    def handlers(self):
        # Prevent adding multiple handlers if logger already configured
        if not self.logger.hasHandlers():
            # File handler
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(self.file_level)
            file_formatter = logging.Formatter(
                "[%(asctime)s::%(filename)s::%(lineno)d::%(funcName)s()] %(levelname)s: %(message)s", 
                    datefmt='%Y-%m-%dT%H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)

            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.console_level)
            console_formatter = logging.Formatter(
                '%(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)

            # Add handlers to logger
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def get_logger(self):
        """ Return the configured logger instance.
        """
        self.handlers()
        return self.logger

    def rotate_old_logs(self, logfile):
        """ Rename log file if already exists and continues in a fresh file.
        """
        if os.path.exists(logfile):
            ct = os.path.getctime(logfile)
            dt = datetime.datetime.fromtimestamp(ct).strftime('%Y%m%dT%H%M%S')
            os.rename(logfile, f"{logfile}.{dt}")
        return 0

class Utils:

    def __init__(self):
        pass

    def check_ip_online(self, ip):
        logger = Logger().get_logger()
        logger.debug(f"NOTE: Pinging { ip }")
        response = os.system(f"ping -c 1 -q { ip }")
        return response == 0


class Paths:

    def __init__(self, inputVars):
        self.purge_files_in_directory(inputVars.paths.output_files)
        self.create_dir_if_not_exist(inputVars.paths.output_files)
        self.create_dir_if_not_exist(inputVars.paths.output_run)
        self.path_run = os.getcwd()+"/"+inputVars.paths.output_run
        self.path_files = os.getcwd()+"/"+inputVars.paths.output_files
        if os.path.exists(self.path_run+"/output.log"):
            os.remove(self.path_run+"/output.log")
        if self.path_run[-1:] != "/":    # if trailing slash is missing, add it to the path_run string
            self.path_run = self.path_run+"/"

    def create_dir_if_not_exist(self, directory):
        if not os.path.exists(directory):
            os.makedirs(directory)

    def purge_files_in_directory(self, dir):
        logger = Logger().get_logger()
        for file in os.listdir(dir):
            file_path = os.path.join(dir, file)
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to delete { file_path }. Reason: { e }")


class Vars:
    def __init__(self):
        self.inputVars = BaseConfig(parse_config('Vars/input.yaml'))


class Convert:

    def __init__(self, speed):
        self.speed = speed
        self.bps = self.from_mbps_to_bps()
        self.kbps = self.from_kbps_to_bps()

    def from_mbps_to_bps(self):
        self.bps = int(self.speed)*1000000
        return self.bps

    def from_kbps_to_bps(self):
        self.kbps = int(self.speed)*1000
        return self.kbps


class NetboxAPI:

    def __init__(self, inputVars):
        ''' Open an initial session to Netbox.
        '''
        logger = Logger().get_logger()
        logger.debug(f"::Pulling data from Netbox API [{ inputVars.netbox.ipv4 }]")
        self.inputVars = inputVars
        counter = self.inputVars.repeat_counter
        while counter >= 0:
            try:
                self.netbox = NetBox(host=inputVars.netbox.ipv4, port=inputVars.netbox.port,
                                    use_ssl=inputVars.netbox.use_ssl, auth_token=inputVars.netbox.token_ro)
            except:
                logger.error(f"  ... attempting to connect... { self.inputVars.repeat_counter - counter +1 }/"
                      f"{ self.inputVars.repeat_counter + 1}")
            sleep(1)
            counter -= 1
        return None

    def get_devices_dict(self, hostname=None):
        ''' Get the device dictionary based on hostname input.
            Input: hostname (string)
            Output: device (dictionary)
        '''
        logger = Logger().get_logger()
        logger.debug(f"  ... Getting devices data for { hostname }.")
        counter = self.inputVars.repeat_counter
        while counter >= 0:
            try:
                return self.netbox.dcim.get_devices(name=hostname)
            except:
                logger.error(f"    ... attempting to connect... { self.inputVars.repeat_counter - counter +1 }/"
                      f"{ self.inputVars.repeat_counter + 1}")
            sleep(1)
            counter -= 1
        logger.error(f"      ... Cannot connect to Netbox!")

    def get_devices_dict_by_params(self, **kwargs):
        ''' Get the device dictionary based on provided parameters as input.
            Input: variuos parameters (dictionary)
            Output: device (dictionary)
        '''
        logger = Logger().get_logger()
        logger.debug(f"  ... Getting devices data on these parameters {kwargs}")
        final_list = []
        for kwarg in kwargs:
            if type(kwargs[kwarg]) == list:
                for i in kwargs[kwarg]:
                    final_list.append(f"{kwarg}={i}")
            else:
                final_list.append(f"{kwarg}={kwargs[kwarg]}")
        # print(final_list)
        counter = self.inputVars.repeat_counter
        while counter >= 0:
            try:
                return self.netbox.dcim.get_devices(**kwargs)
            except:
                logger.error(f"    ... attempting to connect... { self.inputVars.repeat_counter - counter +1 }/"
                      f"{ self.inputVars.repeat_counter + 1}")
            sleep(1)
            counter -= 1
        logger.error(f"      ... Cannot connect to Netbox!")

    def get_circuits_dict(self):
        ''' Netbox/menu/circuits
        Retrieve circuits data as json
        '''
        logger = Logger().get_logger()
        logger.debug(f"  ... Getting circuits data.")
        counter = self.inputVars.repeat_counter
        while counter >= 0:
            try:
                return self.netbox.circuits.get_circuits()
            except:
                logger.error(f"    ... attempting to connect... { self.inputVars.repeat_counter - counter +1 }/"
                      f"{ self.inputVars.repeat_counter + 1}")
            sleep(1)
            counter -= 1
        logger.error(f"      ... Cannot connect to Netbox!")

    def get_site_id_from_device_name(self, device_name, devices):
        ''' Provide api/dcim/devices device name on input.
        Outputs site ID where the device is located.
        '''
        for device in devices:
            if device['name'] == device_name:
                return device['site']['id']

    def get_circuit_speed_from_ckt_menu_based_on_site_id(self, site_id, circuits):
        ''' Provide site_id from Netbox on Input.
        Outputs circuit speed.
        For this module to work a custom_field 'cf_site' and 'cf_speed' must be 
        defined in Netbox Customization menu and active in menu/Circuits.
        '''
        for circuit in circuits:
            if circuit['custom_fields']['cf_site']['id'] == site_id:
                return circuit['custom_fields']['cf_speed']

    def get_circuit_speed_from_sites_menu(self, site_id):
        ''' Return ckt speed which is defined as custom field
        in menu/Sites.
        A custom field 'cf_speed' needs to be defined and active in menu/Sites.
        '''
        logger = Logger().get_logger()
        logger.debug(f"  ... Getting site data for Site ID { site_id }.")
        counter = self.inputVars.repeat_counter
        while counter > 0:
            try:
                return self.netbox.dcim.get_sites(id=site_id)[0]['custom_fields']['cf_speed']
            except TypeError:
                logger.error(f"    ... does the integer value exist at the position of cf_speed field?")
                counter = 0
                return 0
            except:
                logger.error(f"    ... attempting to connect... { self.inputVars.repeat_counter - counter +1 }/"
                      f"{ self.inputVars.repeat_counter + 1}")
            sleep(1)
            counter -= 1
        logger.error(f"      ... Cannot connect to Netbox!")