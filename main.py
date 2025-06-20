import netmiko
import json
from netmiko import ConnectHandler
import iperf3
from multiprocessing import Process
import multiprocessing
import time
import datetime
import os
import logging
import argparse
from argparse import RawTextHelpFormatter
from Libs.Functions import Paths
from Libs.Functions import Logs
from Libs.Functions import NetboxAPI
from Libs.Functions import Vars
from Libs.Functions import Convert
from Libs.Functions import Utils
import re
import sys
from pprint import pprint


def get_forti_commands(inputVars, fg_ip, fg_type_slug):
    intf = "WAN"
    if any(substring in fg_type_slug for substring in ['-60f']):
        intf = "wan1"
    if any(substring in fg_type_slug for substring in ['-40f']):
        intf = "wan"
    if any(substring in fg_ip for substring in ['10.52.22.']):   # if loopback range (new approach with 172.22.52.0/32 for wan)
        intf = "Loopback0"
    return([
        f"diagnose traffictest client-intf {intf}",
        f"diagnose traffictest server-intf {intf}",
        f"diagnose traffictest port { inputVars.iperf3_server.port }",
        f"diagnose traffictest run -c { inputVars.iperf3_server.ipv4 } -B {fg_ip} -J"
    ])

def get_clients_list(clients_list_file):
    try:
        ips = []
        with open(clients_list_file, 'r') as file:
            fileLines = file.read().splitlines()
        for line in fileLines:
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', line):
                # ips.append(line.split("/")[0])  # can add IPs in CIDR format
                ips.append(line)
        return ips
    except FileNotFoundError:
        print("Clients list file not found.")
        sys.exit(0)

def print_app_info(clients_lst, commands_lst, paths, output_file):
    print("=======================================================================================================================")
    print(f"=== FOLLOWING DEVICES' INFO WILL BE FETCHED: { clients_lst }")
    print(f"=== TOTAL NUMBER OF DEVICES TO BE FETCHED: { len(clients_lst) }")
    print("=======================================================================================================================")
    print(f"=== FOLLOWING COMMANDS WILL BE ISSUED: { commands_lst }")
    print("=======================================================================================================================")
    print(f"=== RUN OUTPUT CAN BE VIEWED AT:     tail -f { paths.path_run }output.log")
    print("=======================================================================================================================")
    print(f"=== OUTPUT FILES CAN BE VIEWED AT:     tail -f { paths.path_files }/")
    print("=======================================================================================================================")
    print(f"=== OUTPUT FILE STORED AT:     { output_file }")
    print("=======================================================================================================================")
    return 0

def run_iperf3_server(inputVars, fortigate_ip):
    print(f"::Running test on Fortigate IP { fortigate_ip }\n "+
          " ... Iperf3 Server has been started.")
    server = iperf3.Server()
    server.bind_address = f'{inputVars.iperf3_server.ipv4}'
    server.port = f'{inputVars.iperf3_server.port}'
    server.verbose = True
    result = server.run()

def run_iperf3_client(inputVars, fortigate_ip, commands_lst, path, time_start):
    fortigate = {
        'device_type': 'fortinet', 
        'ip': fortigate_ip, 
        'username': inputVars.fortigate.username, 
        'password': inputVars.fortigate.password, 
        'secret': inputVars.fortigate.password, 
        'verbose': False,
        'ssh_config_file': '~/.ssh/config'
    }
    try:
        print(f"  ... Iperf3 Client has been started.")
        device_session = ConnectHandler(**fortigate)
        device_session.ansi_escape_codes = False
        device_session.enable()
        for x in commands_lst:
            # use for show commands, produces no output when delay factor less than 3
            output = device_session.send_command(x, delay_factor=2,
                                                read_timeout=60)
            try:
                filepath = path+"/"+fortigate_ip
                if 'diagnose traffictest run -c' in x:
                    with open(filepath,"w") as the_file:
                        the_file.write(output)
                        the_file.write("\r\n")
                        the_file.close()
            except:
                print(f"Cannot write file { filepath }.")
        device_session.disconnect()
        print(f"  ... Iperf3 Client run completed in { round(time.time() - time_start, 2) } secs - OK.")
    except:
        print(f"Connection error to { fortigate_ip }. Forgot to export USER and PASSWORD?")

def get_circuit_speed_from_netbox(device_json, netbox):
    try:
        siteId = device_json[0]['site']['id']
    except:
        print(f"    Q: Does the device exist in Netbox?")
    ckt_speed = netbox.get_circuit_speed_from_sites_menu(siteId)
    ckt_speed_conv = Convert(ckt_speed)
    return ckt_speed_conv.bps

def parse_output_to_final_file(clients_lst, path, netbox_obj):
    # netbox_obj = NetboxAPI(inputVars)
    final_dct = {}
    for ip_orig in clients_lst:
        ip = ip_orig.split('/')[0]
        dict_tmp0 = {}
        # print(path)
        hostName = netbox_obj.get_devices_dict_by_params(primary_ip4=ip_orig)[0]['name']
        device_json  = netbox_obj.get_devices_dict(hostName)
        dict_tmp0['upload_contractual']   = get_circuit_speed_from_netbox(device_json, netbox_obj)
        dict_tmp0['download_contractual'] = get_circuit_speed_from_netbox(device_json, netbox_obj)
        try:
            with open(path+"/"+ip, 'r') as file:
                fileData = file.read()
                jsonData = json.loads(fileData)
            dict_tmp0['upload'] = int(jsonData['end']['sum_sent']['bits_per_second'])
            dict_tmp0['download'] = int(jsonData['end']['sum_received']['bits_per_second'])
        except KeyError:
            print("Check Your firewall settings and IP addresses.")
        except: # json data not found in ip file
            utils = Utils()
            print("WARN: JSON file from device output loading problem. "
                  "Checking device online status...")
            if not utils.check_ip_online(ip):
                print(f"WARN: { hostName } ({ ip }) is offline.")
            dict_tmp0['upload']   = "0"
            dict_tmp0['download'] = "0"
        finally:
            final_dct[hostName] = dict_tmp0
    return final_dct

def write_to_final_file(input, output_file):
    with open(output_file, 'w') as file:
        file.write(str(json.dumps(input, indent=4)))
        file.write("\r\n")

def get_input_vars():
    return Vars()

def update_client_list_from_netbox(netbox_obj, client_list_file):
    ''' Return a list of json firewall data from netbox
    based on filter.
    '''
    # region_id=1 for Slovakia, region_id=3 for Austria, status: Active, role: Firewall, manufacturer: Fortinet, tenant: not SWAN
    fw_list = netbox_obj.get_devices_dict_by_params(
        region_id=1,
        status="active",
        # status="planned",
        # name="SVK-ECOPEZIN-FW",
        role_id=4,
        manufacturer_id=2,
        tenant_id__n=6
        )
    with open(client_list_file, 'w') as file:
        for i in fw_list:
            ip = i['primary_ip4']['address']
            file.write(f"{ip}\n")
    return(fw_list)

if __name__ == '__main__':
    '''
    Run iperf3 server on Linuxbox.
    Run iperf3 client on Fortigate and store output to file.
    '''
    print(f"\n\n### EXECUTION STARTED [{ datetime.datetime.now() }].")
    time_overall_start = time.time()

    # Arguments
    parser = argparse.ArgumentParser(description=
    '''
    Runs iperf3 server on Linuxbox.
    Runs iperf3 client on Fortigate and store output to file.
    Operator to provide output file, final JSON values to be stored. Values in bits_per_second.
    Other Input values are defined in `Vars/input.yaml`, E.g. server IPv4.
    Fortigate Username and Password need to be exported before the script is run:
        export USER='supersecretuser'
        export PASSWORD='supersecretpassword'
    ''',
    epilog="Thanks for using fortigate-iperf3 tool.",
    formatter_class=RawTextHelpFormatter
    )
    # parser._action_groups.pop()
    requiredParser = parser.add_argument_group('Required arguments')
    optionalParser = parser.add_argument_group('Optional arguments')
    requiredParser.add_argument('-c', '--client-list', help='Provide clients list filename. One IP per line.', required=True)
    requiredParser.add_argument('-o', '--output-file', help='File to store the output JSON.', required=True)
    # optionalParser.add_argument('-e', '--env', help='Environmnet variables file. Default .env.')
    args = parser.parse_args()
    # inputVars = BaseConfig(parse_config('Vars/input.yaml'))
    inputVars = get_input_vars().inputVars
    path_all = Paths(inputVars)
    logs = Logs(path_all.path_run)
    paths = path_all.path_run

    netbox_obj = NetboxAPI(inputVars)
    fw_list = update_client_list_from_netbox(netbox_obj, args.client_list)
    # pprint(fw_list)

    # Print basic application information
    clients_lst = get_clients_list(args.client_list)
    print_app_info(clients_lst, get_forti_commands(inputVars, "<source_ip>",\
        "<fortigate_model_slug"), path_all, args.output_file)

    # Define main process of iperf3 server on Linuxbox to be run in background

    # Define side process of iperf3 client on Fortigate
    processes_lst = []
    for client_ip in clients_lst:
        # print(client_ip)
        for fg in fw_list:
            if client_ip == fg['primary_ip']['address']:
                fg_type = fg['device_type']['slug']
                break
        time_start = time.time()
        processServer = Process(target=run_iperf3_server,\
            args=(inputVars, client_ip.split('/')[0]))
        processes_lst.append(processServer)
        processServer.start()
        time.sleep(3)
        processClient = Process(target=run_iperf3_client, args=(inputVars,\
            client_ip.split('/')[0], get_forti_commands(inputVars,\
            client_ip.split('/')[0], fg_type), path_all.path_files, time_start))
        processes_lst.append(processClient)
        processClient.start()
        time.sleep(3)
        # Terminate the processes couple
        for proc in processes_lst:
            proc.join(timeout=240)
            if proc.is_alive():
                print(f"Process taking too long. Skipping {client_ip.split('/')[0]}.")
                proc.terminate()
                break
        print(f"  ... Iperf3 Server has been stopped.")

    # Parse output files for required values
    final_output = parse_output_to_final_file(clients_lst, path_all.path_files, netbox_obj)
    write_to_final_file(final_output, args.output_file)

    print(f"### EXECUTION COMPLETED IN { round(time.time() - time_overall_start, 2) } SECS.")