import util
import machine
import gc
import network
from machine import SPI, Pin 
from mqttClient import MQTTClient
import ujson
import time

cmd = None

def mqtt_callback(client, topic, message):
    global cmd
    """
    Received messages are processed by this callback. exp:
    (b'MNZ2V9ORYG/apitest/control', b"{'msg':'hello'}")
    """
    # print('topic:' + str(topic, 'utf8'))
    # status['geteway_version'] = str(topic, 'utf8').split('/')[1]

    uart0 = machine.UART(0, 115200)
    uart0.write(message, len(message))

    cmd = eval(str(message, 'utf8'))
    # 扫描锁的电量，处理程序放在回调函数外面, 循环里面
    if cmd['cmd'] == 'ScheckStatus':
        return 
    else:
        with open('config.json') as load_f:
            status = ujson.load(load_f)
        if status['gateway_id'] == cmd['data']['gateway_id']:
            util.selectFunction(client, ('MNZ2V9ORYG/{}/event'.format(status['gateway_name'])).encode('ascii'), cmd)
            cmd == None
        cmd = None
        
def mqtt_client(status):
    global cmd
    deviceName = status['gateway_name']

    broker_address = 'iotcloud-mqtt.gz.tencentdevices.com'
    port = 1883

    sub_topic = ('MNZ2V9ORYG/{}/control'.format(deviceName)).encode('ascii')
    evt_topic = ('MNZ2V9ORYG/{}/event'.format(deviceName)).encode('ascii')
    client = MQTTClient(status['mqtt_clientid'], broker_address, port, status['mqtt_user'], status['mqtt_pwd'], 60)

    client.set_callback(mqtt_callback)
    client.connect()
    status['mqtt_pwd'] = ''
    with open("config.json","w") as dump_f:
        ujson.dump(status, dump_f)
        dump_f.close()
    client.subscribe(sub_topic, 1)
    print('MQTT succeed.')

    gc.collect()
    gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
    time.sleep(1)

    # 连接成功后扫描更新信息
    util.monitorKeyboard(client, evt_topic)

    # 设备上线 通知odoo后台
    mesg = '{{"type": 3, "cmd": "devOnline", "data": {{"gateway_id": "{}"}}}}'.format(status['gateway_id'])
    client.publish(evt_topic, mesg)

    ticks = 0
    gc.collect()
    gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
    # 键盘自动化测试
    util.send('#3#001#@')
    while True:
        if cmd != None:
            util.selectFunction(client, evt_topic, cmd)
            cmd = None
        time.sleep_ms(20)
        client.check_msg()
        
        ticks += 1

        if ticks >= (60 / 2):
            client.ping()
            gc.collect()
            gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
            ticks = 0