import ujson
import gc
import network
import machine
import utime
import time
import ubinascii
import socket
from ure import compile
from mqtt import mqtt_client

status = {
    "gateway_id": "W001000121000002",
    "gateway_name": "",
    "ssid": "",
    "skey": "",
    "gateway_mac": "",
    "gateway_port": "80",
    "gateway_version": "1",
    "gateway_power": "",
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
    status['gateway_port'] = '81'

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

def parseHeader(headerLine, ):
    kwDict = {}
    reg_content = '''
HTTP/1.x 200 ok
Content-Type: text/html

'''
    with open('index.html', 'r', encoding='utf8') as f:
        reg_content += f.read()
        f.close()

    # print(headerLine)
    # time.sleep(1)  # wait 1 seconds 
    bytesline = headerLine
    headerLine = headerLine.decode('ascii')
    print(headerLine)

    if headerLine.find('GET /index') >= 0:
        return reg_content

    if headerLine.find('?') >= 0:
        _percent_pat = compile(b'%[A-Fa-f0-9][A-Fa-f0-9]')
        hex_to_byte = lambda match_ret: \
                  ubinascii.unhexlify(match_ret.group(0).replace(b'%', b'').decode('ascii'))

        bytesline = _percent_pat.sub(hex_to_byte, bytesline)
        headerLine = bytesline.decode('ascii')

        print('1', headerLine)
        headerLine = headerLine.split('?')[1]
        headerLine = headerLine.split(' ')[0]
        print('2', headerLine)
        lists = headerLine.split('&')
        for kw in lists:
            kwlist = kw.split('=')
            kwDict[kwlist[0]] =  kwlist[1]
            print('3', kwlist[1])

        return kwDict

def httpServer():
    global status
    bodyLen = None
    
    template = """HTTP/1.1 200 OK Content-Length: {length}

{json}"""
    reqDict = {}
    cb = None
    needReset = False
    addr = socket.getaddrinfo('0.0.0.0', int(status['gateway_port']))[0][-1]


    s = socket.socket()
    s.bind(addr)
    s.listen(1)

    print('listening on', addr)


    while True:
        flag = 0
        cl, addr = s.accept()

        cl_file=cl.makefile('rwb',0)


        while True:
            print('param.')
            line = cl_file.readline()
            ret = parseHeader(line)

            if ret:
                if type(ret) != type('str'):
                    print('ret')
                    reqDict = ret
                    print(reqDict)
                else:
                    print(ret)
                    time.sleep(1)  # wait 1 seconds
                    cl.sendall(ret.encode())
                    # cl.close()
                    line = None
                    flag = 1
                    continue

            if (not line) or (line == b'\r\n'):
                break
        if flag:
            continue
        if 'callbacks' in reqDict.keys():
            cb = reqDict['callbacks']
            # print('4', cb)
        
        for key in status:
            if key in reqDict.keys():
                status[key] = reqDict[key]
                needReset = True
                print('5', key)

        saveJson()
        reqDict = {}

        if cb:
            data = "{}('{}')" .format(cb, ujson.dumps(status))
            cb = None
        else:
            data = ''

        response = template.format(length=len(data), json=data)


        time.sleep(1)  # wait 1 seconds
        cl.send(response)
        cl.close()



        if needReset:
            time.sleep(1)  # wait 1 seconds                
            machine.reset()


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
    global status
    template = """POST /api/xiaosun/getMqttInfo/?gateway_id={gateway_id}&gateway_mac={gateway_mac}HTTP/1.1
User-Agent: PostmanRuntime/7.28.3
Accept: */*
Postman-Token: c4aed8d3-ba08-4fd2-86f3-d41dbb9f3511
Host: erp.xiao-sun.cn
Accept-Encoding: gzip, deflate, br
Connection: keep-alive
Cookie: session_id=7e3d6ffc4143178ea40ef16015ab764ac9e02b6f
Content-Length: 0

"""
    req = template.format(gateway_id=status['gateway_id'], gateway_mac=status['gateway_mac'])
    triple = http_post('http://erp.xiao-sun.cn/api/xiaosun/getMqttInfo/', req)
    # print(triple['msg'])
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

    if sta_if.isconnected():
        print('Wifi Connection successful.')
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
        # uos.dupterm(None, 1) # disable REPL on UART(0)
        client_id, USER, PWD = login()
        if client_id:
            status['mqtt_clientid'] = client_id
            status['mqtt_user'] = USER
            status['mqtt_pwd'] = PWD
        saveJson()
        mqtt_client(status)
    elif status['gateway_port'] == '80':
        ap_if.active(True)
        sta_if.active(False)
        httpServer()
    else:                             # AP Mode
        print('Wifi Connection failed.Set hotspot mode...')
        ap_if.active(True)
        sta_if.active(False)
        status['gateway_port'] = '80'
        httpServer()