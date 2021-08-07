import socket
import ujson
import gc
import network
import machine
import utime
import time
from json_util import status, createJson, saveJson
from mqtt import mqtt_client
from httpserver import httpServer

def http_post(url, req):
    jstr = ''
    _, _, host, path = url.split('/', 3)

    host = host.split(':')
    if len(host) == 2:
		addr = socket.getaddrinfo(host[0], int(host[1]))[0][-1]
    else:
		addr = socket.getaddrinfo(host[0], 80)[0][-1]

    s = socket.socket()
    s.connect(addr)
    s.send(bytes(req, 'utf8'))
    while True:
		data = s.recv(100)
		if data:
			jstr += str(data, 'utf8')
		else:
			break
    s.close()

    jstr = jstr.split('\r\n\r\n')
    if len(jstr) == 2:
		return ujson.loads(jstr[1])
def login():
    template = '''POST /xiaosun/getMqttInfo/ HTTP/1.1
Accept: */*
Host: 192.168.52.36:8014
Accept-Encoding: gzip, deflate, br
Connection: keep-alive
Content-Type: application/x-www-form-urlencoded
Content-Length: {length} 
Cookie: frontend_lang=zh_CN; session_id=767a0763e8312a1dfa9e612c4be6aeae0864faa5

{data}'''
    data = 'gateway_id={}&gateway_mac={}&gateway_power={}&gateway_version={}'.format(status['gateway_id'],
    status['gateway_mac'], status['gateway_power'],status['gateway_version'])
    req = template.format(length=len(data), data=data)
    triple = http_post('http://192.168.52.36:8014/xiaosun/getMqttInfo/', req)
    print(triple['msg'])
    triple = triple['msg']

    if not triple:
		return None, None, None

    client_id = triple["mqtt_clientid"]
    USER = triple["mqtt_user"]
    PWD = triple["mqtt_pwd"]
    # 同步服务器时间
    tm = tuple(triple["server_time"])
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))

    return client_id, USER, PWD

if __name__ == '__main__':
    try:
        with open("config.json",'r') as load_f:
            status = ujson.load(load_f)
        load_f.close()
    except OSError:
        createJson()

    ap_if = network.WLAN(network.AP_IF)
    sta_if = network.WLAN(network.STA_IF)
    if status['ssid'] == '' or status['skey'] == '':      # AP Mode
        ap_if.active(True)
        sta_if.active(False)
    else:                       # STA Mode
        ap_if.active(False)
        sta_if.active(True)
        sta_if.connect(status['ssid'], status['skey'])
        time.sleep(10)  # try 10 seconds
        sta_if.ifconfig()

    if status['gateway_port'] == '80':
        httpServer()
    elif sta_if.isconnected():
        print('Wifi Connection successful.')
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
        # uos.dupterm(None, 1) # disable REPL on UART(0)
        # client_id, USER, PWD = login()
        # if client_id:
        #     status['mqtt_clientid'] = client_id
        #     status['mqtt_user'] = USER
        #     status['mqtt_pwd'] = PWD
        mqtt_client(status)
    else:                             # AP Mode
        print('Wifi Connection failed.Set hotspot mode...')
        ap_if.active(True)
        sta_if.active(False)
        status['gateway_port'] = '80'
        httpServer()