import ujson
import time
from machine import Pin, SPI

ble_json = 'devices.json'
gate_json = 'config.json'

check_flag = 1
check_id = None

spi = SPI(baudrate=5000, polarity=0, phase=0, sck=Pin(16), mosi=Pin(14), miso=Pin(12),bits=8)
cs_pin = Pin(13,Pin.OUT)
r_pin = Pin(5,Pin.IN)

# 读取json文件
def readJson(file_name):
	try:
		with open(file_name, mode='r', encoding='utf-8') as load_f:
			dl = ujson.load(load_f)
			load_f.close()
			return dl
	except OSError:
		return -1
# 配置所有锁的信息
def updateAllLockInfo(data):
	devs = []
	for i in data:
		del i['lock_status']
		devs.append(i)
	if devs == []:
		return "failed"
	all_dev = {}
	all_dev['Devices'] = devs
	all_dev['lock_admin_rkey'] = data[0]['lock_admin_rkey']
	dev_json = ujson.dumps(all_dev)
	try:
		with open(ble_json, mode='w', encoding='utf-8') as f:
			f.write(dev_json)
			f.close()
			return 1
	except Exception as e:
		return -1
# 配置指定锁的信息
def updateLockInfo(data):
	del data['lock_status']
	all_ = readJson(ble_json)
	dl = all_['Devices']
	for i in dl:
		if i['lock_mac'] == ''.join(data['lock_mac'].split(':')):
			i = data
	all_['Devices'] = dl
	dev_json = ujson.dumps(all_)
	try:
		with open(ble_json, mode='w', encoding='utf-8') as f:
			f.write(dev_json)
			f.close()
			return 1
	except Exception as e:
		return -1
# 处理键盘设备传输的指令
def responseKeyword(client, topic, mesg):
	global check_id, check_flag
	pwd_type = None
	lock_mac = None
	report = '{{"type": 2, "data": {{"datetime": "{}", "passwd_type": "{}", "lock_mac": "{}"}}, "cmd": "{}"}}'
	tm = time.localtime()
	if mesg[1:4] == '200':
		report = report.format(tm, pwd_type, lock_mac, "unlock_successed")
	elif mesg[1:4] == '201':
		report = report.format(tm, pwd_type, lock_mac, "lock_successed")
	elif mesg[1:4] == '202':
		updateLockStatus(check_id, mesg[5:7], str(int('0x' + mesg[7:11])) + 'mA')
		check_flag = 1
	elif mesg[1:4] == '290':
		pwd_type, lock_mac = matchPasswd(mesg[5:11])
		report = report.format(tm, pwd_type, lock_mac, "successed") if pwd_type else report.format(tm, pwd_type, lock_mac, "CuserStorage")
	elif mesg[1:4] == '400':
		updateLockStatus(check_id, '0', '0mA')
		check_flag = 1
	client.publish(topic, report)
# 向键盘设备发送指令
def send(data) :
	cs_pin.value(0)
	spi.write(bytearray(data.encode("utf-8")))
	cs_pin.value(1)
# 读取键盘设备传输的指令
def read(client, topic):
	cs_pin.value(0)
	buf = bytearray(26)
	spi.readinto(buf) 
	cs_pin.value(1)
	print(str(buf, 'utf8'))
	if buf[0] == 35:
		responseKeyword(client, topic, str(buf,'utf8'))
# 向锁发送指令 扫描指定锁状态 电量
def checkLockEQStatu():
	global check_flag, check_id
	t1 = time.time()
	for i in readJson(ble_json)['Devices']:
		check_id = i['lock_id']
		while True:
			t2 = time.time()
			if check_flag:
				send("#3#271#{}#@".format(check_id))
				check_flag = 0
				break
			elif check_flag == 0 and (t2 - t1 >= 10):
				check_flag = 1
				t1 = t2
				break
# 初始化SPI
def monitorKeyboard(client, topic):
	def funv(v):
		read(client, topic)
	cs_pin.value(1)
	r_pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING , handler=funv)
# 返回所有的蓝牙设备信息
def getDevicesInfo(data):
	all_dev_info = {'type': 2, 'cmd': 'successed'}
	all_dev_info["data"] = readJson(ble_json)['Devices']
	if all_dev_info == {}:
		return -1
	return ujson.dumps(all_dev_info)
# 返回指定蓝牙设备信息
def getDeviceInfo(data):
	mac = data['lock_mac']
	dev_info = {'type': 2, 'cmd': 'successed'}
	all_dev_info = readJson(ble_json)['Devices']
	for i in all_dev_info:
		if i['lock_mac'] == ''.join(mac.split(':')):
			dev_info['data'] = i
	if dev_info == {}:
		return -1
	return ujson.dumps(dev_info)
# 检查所有设备状态
def checkAllDevicesStatus():
	status = {'type': 3, 'cmd': 'CheartBeat'}
	dl = readJson(ble_json)['Devices']
	devs = []
	for i in dl:
		del i['lock_mac']
		del i['lock_grid_info']
		del i['lock_rkey']
		del i['lock_ckey']
		devs.append(i)
	dev = {}
	gate_all_info = readJson(gate_json)
	dev['gateway_id'] = gate_all_info['gateway_id']
	dev['gateway_power'] =  gate_all_info['gateway_power']
	ble_dev = {'lock': devs}
	gate_dev = {'gateway': dev}
	
	status['data'] = [ble_dev, gate_dev]
	return ujson.dumps(status)
# 更新锁状态
def updateLockStatus(check_id, lock_statu, lock_eq):
	all_ = readJson(ble_json)
	dl = all_['Devices']
	for i in dl:
		if i['lock_id'] == check_id:
			i['lock_physical_state'] = lock_statu
			i['lock_EQ'] = lock_eq
	all_['Devices'] = dl
	dev_json = ujson.dumps(all_)
	try:
		with open(ble_json, mode='w', encoding='utf-8') as f:
			f.write(dev_json)
			f.close()
			return 1
	except Exception as e:
		return -1
# 更新密码
def changePasswd(data):
	all_ = readJson(ble_json)
	dl = all_['Devices']
	for i in dl:
		if i['lock_mac'] == ''.join(data['lock_mac'].split(':')):
			i['lock_rkey'] = data['lock_rkey']
			i['lock_ckey'] = data['lock_ckey']
	all_['Devices'] = dl
	dev_json = ujson.dumps(all_)
	try:
		with open(ble_json, mode='w', encoding='utf-8') as f:
			f.write(dev_json)
			f.close()
			return 1
	except Exception as e:
		return -1
# 单开锁
def unlock(data):
	send('#0#270#{}#@'.format(''.join(data['lock_mac'].split(":"))))
	return 1
# 单关锁
def lock(data):
	send('#1#270#{}#@'.format(''.join(data['lock_mac'].split(":"))))
	return 1
# 开关锁
def dlock(data):
	send('#2#270#{}#@'.format(''.join(data['lock_mac'].split(":"))))
	return 1
# 密码匹配
def matchPasswd(request_passwd):
	dl = readJson(ble_json)['Devices']
	lock_mac = None
	pwd_type = None
	for i in dl:
		cor_pwd1 = i['lock_grid_info'] + i['lock_rkey']  
		cor_pwd2 = i['lock_grid_info'] + i['lock_ckey']  
		if (cor_pwd1 == request_passwd) or (cor_pwd2 == request_passwd):
			# print('Passwd OK.')
			lock_mac = i['lock_mac']
			pwd_type = "rkey" if  (cor_pwd1 == request_passwd) else "ckey"
			data = '#2#270#{}#@'.format(i['lock_mac'])
			send(data)
			# print('send data: {}'.format(data))
			return pwd_type, lock_mac
	return pwd_type, lock_mac
# 根据Odoo后台下发指令进行操作
def selectFunction(client, topic, data):
	func_dict = {"SlocksConfig": updateAllLockInfo,
	"SlockConfig": updateLockInfo,
	"SqueryLocksStatus": getDevicesInfo,
	"SqueryLockStatus": getDeviceInfo,
	"SchangePasswd": changePasswd,
	"Sunlock": unlock,
	"Slock": lock,
	"Sdlock": dlock
	}
	mesg = '{{"type": 2, "cmd": "{}"}}'
	if data['cmd'] not in func_dict.keys():
		mesg = mesg.format("cmdNotFound")
		client.publish(topic, mesg)
		return 
	result = func_dict.get(data["cmd"])(data['data'])
	if result == 1:
		mesg = mesg.format("success")
	elif result == -1:
		mesg = mesg.format("failed")
	else:
		mesg = result
	client.publish(topic, mesg)