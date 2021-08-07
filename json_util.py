import ujson
status = {
    "gateway_id": "W001000121000001",
    "gateway_name": "Wb3733000",
    "ssid": "gf1969",
    "skey": "qcgsnb1969",
    "gateway_mac": "b4e62d3073b0",
    "gateway_port": "80",
    "gateway_version": "1",
    "gateway_power": "3500mA",
    "mqtt_clientid": "",
    "mqtt_user": "",
    "mqtt_pwd": "",
    "mqtt_skey": ""
}




def createJson():
    global status
    
    status['gateway_name'] = 'W' + ubinascii.hexlify(machine.unique_id()).decode('ascii')

    ap = network.WLAN(network.AP_IF)
    status['gateway_mac'] = ubinascii.hexlify(ap.config('mac')).decode('ascii')

    with open("config.json","w") as dump_f:
        ujson.dump(status, dump_f)
    time.sleep(1)  # wait 1 seconds

    ap.active(True)
    ap.config( essid = '{}'.format(status['gateway_name']), password = 'harmonie' )
    time.sleep(1)  # wait 1 seconds

    machine.reset()

def saveJson():
    global status
    with open("config.json","w") as dump_f:
        ujson.dump(status, dump_f)
    time.sleep(1)  # wait 1 seconds