import ujson
import time
from machine import Pin, SPI

ble_json = 'dev.json'
gate_json = 'config.json'

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
		dev = {}
		dev['lock_mac'] = ''.join(i['lock_mac'].split(':'))
		dev['lock_id'] = i['lock_id']
		dev['lock_grid_info'] = i['lock_grid_info']
		dev['lock_version'] = i['lock_version']
		dev['lock_rkey'] = i['lock_rkey']
		dev['lock_ckey'] = i['lock_ckey']
		dev['lock_physical_state'] = i['lock_physical_state']
		dev['lock_EQ'] = i['lock_EQ']
		devs.append(dev)
	if devs == []:
		return -1
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
		return -2
# 配置指定锁的信息
def updateLockInfo(data):
	all_ = readJson(ble_json)
	dl = all_['Devices']
	for i in dl:
		if i['lock_mac'] == ''.join(data['lock_mac'].split(':')):
			i['lock_grid_info'] = data['lock_grid_info']
			i['lock_version'] = data['lock_version']
			i['lock_rkey'] = data['lock_rkey']
			i['lock_ckey'] = data['lock_ckey']
			i['lock_physical_state'] = data['lock_physical_state']
			i['lock_EQ'] = data['lock_EQ']
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
	pwd_type = None
	lock_mac = None
	report = '{{"type": 2, "data": {{"datetime": "{}", "passwd_type": "{}", "lock_mac": "{}"}}, "cmd": "{}"}}'
	tm = time.localtime()
	# 监听键盘设备是否有密码返回
	if mesg[:5] == '#290#':
		pwd_type, lock_mac = matchPasswd(mesg[5:11])
		report = report.format(tm, pwd_type, lock_mac, "successed") if pwd_type else report.format(tm, pwd_type, lock_mac, "unlock_failed")
	elif mesg[:5] == '#200#':
		report = report.format(tm, pwd_type, lock_mac, "unlock_successed")
	elif mesg[:5] == '#201#':
		report = report.format(tm, pwd_type, lock_mac, "lock_successed")
	elif mesg[:5] == '#000#':
		print('51822 Started.')
	client.publish(topic, report)
# 向键盘设备发送指令
def send(data) :
	cs_pin.value(0)
	buf = bytearray(data.encode("utf-8"))
	spi.write(buf)
	cs_pin.value(1)
# 读取键盘设备传输的指令
def read(client, topic):
	cs_pin.value(0)
	buf = bytearray(26)
	spi.readinto(buf) 
	cs_pin.value(1)
	print(buf)
	if buf[0] == 35:
		mesg =str(buf,'utf8')
		responseKeyword(client, topic, mesg)
		return mesg
	return None
def monitorKeyboard(client, topic):
	def funv(v):
		spi_buf = read(client, topic)
	cs_pin.value(1)
	r_pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING , handler=funv)
# 返回所有的蓝牙设备信息
def getDevicesInfo():
	all_dev_info = {}
	dl = readJson(ble_json)['Devices']
	all_dev_info["data"] = dl
	all_dev_info["type"] = 2 
	all_dev_info["cmd"] = "successed" 
	if all_dev_info == {}:
		return -1
	return ujson.dumps(all_dev_info)
# 返回指定蓝牙设备信息
def getDeviceInfo(mac):
	dev_info = {}
	all_dev_info = readJson(ble_json)['Devices']
	for i in all_dev_info:
		if i['lock_mac'] == ''.join(mac.split(':')):
			dev_info['data'] = i
			dev_info['type'] = 2
			dev_info['cmd'] = 'successed' 
	if dev_info == {}:
		return -1
	return ujson.dumps(dev_info)
# 检查所有设备状态
def checkAllDevicesStatus():
	status = {}
	dl = readJson(ble_json)['Devices']
	devs = []
	for i in dl:
		dev = {}
		dev['lock_id'] = i['lock_id']
		dev['lock_version'] = i['lock_version']
		dev['lock_physical_state'] = i['lock_physical_state']
		dev['lock_EQ'] = i['lock_EQ']
		devs.append(dev)
	dev = {}
	gate_all_info = readJson(gate_json)
	dev['gateway_id'] = gate_all_info['gateway_id']
	dev['gateway_power'] =  gate_all_info['gateway_power']
	ble_dev = {}
	gate_dev = {}
	ble_dev["lock"] = devs
	gate_dev["gateway"] = dev
	
	status['data'] = [ble_dev, gate_dev]
	status['type'] = 3
	status['cmd'] = 'CheartBeat'
	return ujson.dumps(status)
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
# 但开锁
def unlock(mac):
	pass
# 单关锁
def lock(mac):
	pass
# 开关锁
def dlock(mac):
	pass
# 密码匹配
def matchPasswd(request_passwd):
	dl = readJson(ble_json)['Devices']
	lock_mac = None
	pwd_type = None
	for i in dl:
		cor_pwd1 = i['lock_grid_info'] + i['lock_rkey']  
		cor_pwd2 = i['lock_grid_info'] + i['lock_ckey']  
		if (cor_pwd1 == request_passwd) or (cor_pwd2 == request_passwd):
			print('Passwd OK.')
			lock_mac = i['lock_mac']
			pwd_type = "rkey" if  (cor_pwd1 == request_passwd) else "ckey"
			data = '#2#270#{}#@'.format(i['lock_mac'])
			send(data)
			print('send data: {}'.format(data))
			return pwd_type, lock_mac
		else:
			print('Passwd Error.')
			return None, None
	return None, None
# 根据Odoo后台下发指令进行操作
def selectFunction(client, topic, data):
	# func_list = {"SlocksConfig": "updateAllLockInfo",
	# "SlockConfig": "updateLockInfo",
	# "SqueryLocksStatus": "getDevicesInfo",
	# "SqueryLockStatus": "getDeviceInfo",
	# "Sunlock": "unlock",
	# "Slock": "lock",
	# "Sdlock": "dlock",
	# "SchangePasswd": "changePasswd"
	# }
	# 配置所有锁的信息
	mesg = '{{"type": 2, "cmd": "{}"}}'
	if data["cmd"] == "SlocksConfig":
		mesg = mesg.format("successed") if updateAllLockInfo(data['data']) == 1 else  mesg.format("failed")
	# 配置指定锁的信息
	elif data["cmd"] == "SlockConfig":
		mesg = mesg.format("successed") if updateLockInfo(data["data"]) == 1 else mesg.format("failed")
	# 查询所有锁的信息
	elif data["cmd"] == "SqueryLocksStatus":
		result = getDevicesInfo()
		mesg = mesg.format("failed") if result == -1 else result
	# 查询指定锁的状态信息
	elif data["cmd"] == "SqueryLockStatus":
		result = getDeviceInfo(data['data']['lock_mac'])
		mesg = mesg.format("failed") if result == -1 else result
	# 单次开锁
	elif data["cmd"] == "Sunlock":
		data = '#0#270#{}#@'.format(''.join(data['data']['lock_mac'].split(":")))
		send(data)
	# 单次上锁
	elif data["cmd"] == "Slock":
		data = '#1#270#{}#@'.format(''.join(data['data']['lock_mac'].split(":")))
		send(data)
	# 开锁又上锁
	elif data["cmd"] == "Sdlock":
		data = '#2#270#{}#@'.format(''.join(data['data']['lock_mac'].split(":")))
		send(data)
	# 修改密码
	elif data["cmd"] == "SchangePasswd":
		result = changePasswd(data['data'])
		mesg = mesg.format("changePasswdFailed") if result == -1 else mesg.format("changePasswdSuccessed")
	client.publish(topic, mesg)