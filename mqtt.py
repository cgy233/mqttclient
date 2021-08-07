import machine
import gc
from machine import SPI, Pin 
from mqttClient import MQTTClient
import time
import util

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
def mqtt_client(status):

    deviceName = status['gateway_name']

    global cmd
    print('MQTT Connecting...')
    broker_address = 'iotcloud-mqtt.gz.tencentdevices.com'
    port = 1883

    client_id = status['mqtt_clientid']
    USER = status['mqtt_user']
    PWD = status['mqtt_pwd']

    sub_topic = ('MNZ2V9ORYG/{}/control'.format(deviceName)).encode('ascii')
    evt_topic = ('MNZ2V9ORYG/{}/event'.format(deviceName)).encode('ascii')

    client = MQTTClient(client_id, broker_address, port, USER, PWD, 60)
    client.set_callback(mqtt_callback)
    client.connect()

    client.subscribe(sub_topic, 1)
    print('Subscription succeeded.')

    util.monitorKeyboard(client, evt_topic)

    gc.collect()
    gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
    time.sleep(1)

    # try:
    ticks = 0
    time1 = time.time()
    while True:
        # 每隔三十秒发送一次所有设备状态信息
        time2 = time.time()
        if int(time2 - time1) >= 30:
            mesg = util.checkAllDevicesStatus()
            print("Check All BLE Devices Status.")
            client.publish(evt_topic, mesg)
            time1 = time2
        
        time.sleep_ms(500)
        client.check_msg()
        
        if cmd != None:
            util.selectFunction(client, evt_topic, cmd)
            cmd = None
        ticks += 1

        time2 = time.time()

        if ticks >= (60 / 2):
            client.ping()
            gc.collect()
            gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
            ticks = 0
    # except Exception as e:
    #     print("Exception:", e)
    # finally:
    #     print('try - finally - disconnect')
    #     client.disconnect()
        # machine.reset()