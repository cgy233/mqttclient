from os import stat
import ujson
import gc
import network
import machine
import time
import ubinascii
import socket
from util import Util
from ure import compile
from mqttClient import MQTTClient
gc.collect()

cmd = None

status = {
    "gateway_id": "",
    "gateway_name": "",
    "ssid": "",
    "skey": "",
    "gateway_mac": "",
    "gateway_port": "80",
    "gateway_version": "1",
    "mqtt_clientid": "",
    "mqtt_user": "",
    "mqtt_pwd": "",
}

# 工具类，初始化SPI，提供各种功能接口
util = Util()

def createJson():
    global status
    
    status['gateway_name'] = 'W' + ubinascii.hexlify(machine.unique_id()).decode('ascii')

    ap = network.WLAN(network.AP_IF)
    status['gateway_mac'] = ubinascii.hexlify(ap.config('mac')).decode('ascii')
    status['gateway_port'] = '80'

    saveJson()

    ap.active(True)
    ap.config(essid = '{}'.format(status['gateway_name']), password = 'harmonie' )
    time.sleep(1)  # wait 1 seconds

    machine.reset()

def saveJson():
    global status
    with open("config.json","w") as dump_f:
        ujson.dump(status, dump_f)
def mqtt_callback(client, topic, message):
    global cmd, status

    # uart0 = machine.UART(0, 115200)
    # uart0.write(message, len(message))
    
    # 容错：103网络错误
    try:
        cmd = eval(str(message, 'utf8'))
        # 只处理属于本网关id的消息
        if status['gateway_id'] == cmd['data']['gateway_id']:
            if cmd['cmd'] == 'ScheckStatus':
                return 
            else:
                util.selectFunction(client, client.evt_topic, cmd)
                cmd = None
                return
        else:
            cmd = None
            return
    except Exception as e:
        machine.reset()
        
def mqtt_client(gateway_id, clinet_id, mqtt_user, mqtt_pwd):
    global cmd
    gc.enable()

    topic = 'MNZ2V9ORYG/{}/'.format(gateway_id)
    sub_topic = (topic + 'control').encode('ascii')
    evt_topic = (topic + 'event').encode('ascii')

    # 容错：网络波动或者mqtt会话结束
    try:
        client = MQTTClient(evt_topic, clinet_id, 'iotcloud-mqtt.gz.tencentdevices.com', 1883, mqtt_user, mqtt_pwd, 120)
        client.set_callback(mqtt_callback)
        client.connect()
        client.subscribe(sub_topic, 1)
        print('MQTT succeed.')
        
        # 设置51键盘操作SPI中断
        util.monitorKeyboard(client, evt_topic, gateway_id)

        # 设备上线 通知odoo后台
        mesg = '{{"cmd": "devOnline", "data": {{"gateway_id": "{}"}}}}'.format(gateway_id)
        client.publish(evt_topic, mesg)

        ticks = 0
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
        util.send('#3#001#@')
        util.send('#3#003#@')
        while True:
            if cmd != None:
                util.selectFunction(client, evt_topic, cmd)
                cmd = None
            time.sleep_ms(200)
            client.check_msg()
            
            ticks += 1

            if ticks >= (50 / 2):
                client.ping()
                gc.collect()
                gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
                ticks = 0
    except Exception as e:
        # MQTT 连接失败，重新向Odoo后台请求MQTT的相关参数
        machine.reset()

def parseHeader(headerLine, ):
    kwDict = {}
    reg_content = '''
HTTP/1.x 200 ok 
Content-Type: text/html

'''
    with open('index.html', 'r', encoding='utf8') as f:
        reg_content += f.read()
        f.close()

    time.sleep(1)
    bytesline = headerLine
    headerLine = headerLine.decode('ascii')

    if headerLine.find('GET /index') >= 0:
        return reg_content

    if headerLine.find('?') >= 0:
        _percent_pat = compile(b'%[A-Fa-f0-9][A-Fa-f0-9]')
        hex_to_byte = lambda match_ret: \
                  ubinascii.unhexlify(match_ret.group(0).replace(b'%', b'').decode('ascii'))

        bytesline = _percent_pat.sub(hex_to_byte, bytesline)
        headerLine = bytesline.decode('ascii')
        headerLine = headerLine.split('?')[1]
        headerLine = headerLine.split(' ')[0]
        lists = headerLine.split('&')

        for kw in lists:
            kwlist = kw.split('=')
            kwDict[kwlist[0]] =  kwlist[1]
        return kwDict
# 热点模式 设置WIFI名称密码
def httpServer():
    global status
    # 通知51 亮红灯
    util.send('#3#002#@')
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

    try:
        while True:
            flag = 0
            cl, addr = s.accept()
            cl_file=cl.makefile('rwb',0)

            while True:
                line = cl_file.readline()
                ret = parseHeader(line)

                if ret:
                    if type(ret) != type('str'):
                        reqDict = ret
                    else:
                        time.sleep(1)  # wait 1 seconds
                        cl.sendall(ret.encode())
                        line = None
                        flag = 1
                        continue
                if (not line) or (line == b'\r\n'):
                    break
            if flag:
                continue
            if 'callbacks' in reqDict.keys():
                cb = reqDict['callbacks']
            
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
                data = '<p>Successfully Set Wifi.<p>'

            response = template.format(length=len(data), json=data)


            time.sleep(1)  # wait 1 seconds
            cl.send(response)
            cl.close()

            if needReset:
                time.sleep(1)  # wait 1 seconds                
                machine.reset()
    except Exception as e:
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
    s.sendall(req.encode())
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
    template = """POST /api/xiaosun/getMqttInfo/ HTTP/1.1
Accept: */*
Host: erp.xiao-sun.cn
Accept-Encoding: gzip, deflate, br
Connection: close
Content-Type: application/x-www-form-urlencoded
Content-Length: {length} 
Cookie: frontend_lang=zh_CN; session_id=767a0763e8312a1dfa9e612c4be6aeae0864faa5

{data}"""
    data = 'gateway_id={}&gateway_mac={}'.format(status['gateway_id'], status['gateway_mac'])
    triple = http_post('http://erp.xiao-sun.cn/api/xiaosun/getMqttInfo/', template.format(length=len(data), data=data))
    
    return triple['msg']

def run():
    global status
    ap_if = network.WLAN(network.AP_IF)
    sta_if = network.WLAN(network.STA_IF)
    try:
        with open("config.json",'r') as load_f:
            status = ujson.load(load_f)
    except OSError:
        createJson()
    if status['ssid'] == '' or status['skey'] == '':      # AP Mode
        ap_if.active(True)
        sta_if.active(False)
    else:                       # STA Mode
        ap_if.active(False)
        sta_if.active(True)
        sta_if.connect(status['ssid'], status['skey'])
        t1 = time.time()
        while True:
            t2 = time.time()
            if sta_if.isconnected():
                sta_if.ifconfig()
                break
            if t2 - t1 >= 8:
                break
            time.sleep_ms(20)
            t2 = t1

    if sta_if.isconnected():
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
        time.sleep(1)
        if status['mqtt_pwd'] == '':
            # 配置or更新mqtt用户名、密码
            result = login()
            status['mqtt_clientid'] = result["mqtt_clientid"]
            status['mqtt_user'] = result["mqtt_user"]
            status['mqtt_pwd'] = result["mqtt_pwd"]
            status['gateway_id'] = result["gateway_id"]
            # 同步服务器时间
            tm = tuple(result["server_time"])
            machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3] + 8, tm[4], tm[5], 0))
            saveJson()
        mqtt_client(status['gateway_id'], status['mqtt_clientid'], status['mqtt_user'], status['mqtt_pwd'])
    else:
        # AP MODE
        ap_if.active(True)
        sta_if.active(False)
        ap_if.config(essid = '{}'.format(status['gateway_name']), password = 'harmonie')
        status['gateway_port'] = '80'
        httpServer()

if __name__ == '__main__':
    run()