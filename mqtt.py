import util
import machine
import gc
import network
from machine import SPI, Pin 
from mqttClient import MQTTClient
import ujson
import time

cmd = None
gate_id = None
gate_name = None

def mqtt_callback(client, topic, message):
    global cmd, gate_id, gate_name
    """
    Received messages are processed by this callback. exp:
    (b'MNZ2V9ORYG/apitest/control', b"{'msg':'hello'}")
    """

    # uart0 = machine.UART(0, 115200)
    # uart0.write(message, len(message))

    cmd = eval(str(message, 'utf8'))
    # 扫描锁的电量，处理程序放在回调函数外面, 循环里面
    if gate_id == cmd['data']['gateway_id']:
        if cmd['cmd'] == 'ScheckStatus':
            return 
        else:
            util.selectFunction(client, ('MNZ2V9ORYG/{}/event'.format(gate_name)).encode('ascii'), cmd)
            cmd = None
            return
    else:
        cmd = None
        return
        
def mqtt_client():
    global cmd, gate_id, gate_name
    gc.enable()
    with open('config.json') as load_f:
        statu = ujson.load(load_f)

    gate_id = statu['gateway_id']
    gate_name = statu['gateway_name']

    broker_address = 'iotcloud-mqtt.gz.tencentdevices.com'
    port = 1883

    sub_topic = ('MNZ2V9ORYG/{}/control'.format(gate_name)).encode('ascii')
    evt_topic = ('MNZ2V9ORYG/{}/event'.format(gate_name)).encode('ascii')
    client = MQTTClient(statu['mqtt_clientid'], broker_address, port, statu['mqtt_user'], statu['mqtt_pwd'], 60)

    client.set_callback(mqtt_callback)
    client.connect()
    client.subscribe(sub_topic, 1)
    print('MQTT succeed.')

    time.sleep(1)

    # 连接成功后扫描更新信息
    util.monitorKeyboard(client, evt_topic)

    # 设备上线 通知odoo后台
    mesg = '{{"type": 3, "cmd": "devOnline", "data": {{"gateway_id": "{}"}}}}'.format(statu['gateway_id'])
    del statu
    client.publish(evt_topic, mesg)

    ticks = 0
    gc.collect()
    gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
    util.send('#3#001#@')
    while True:
        if cmd != None:
            util.selectFunction(client, evt_topic, cmd)
            cmd = None
        time.sleep_ms(200)
        client.check_msg()
        
        ticks += 1

        if ticks >= (60 / 2):
            client.ping()
            gc.collect()
            gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
            ticks = 0