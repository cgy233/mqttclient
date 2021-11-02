import ujson
import time
import machine
from machine import Pin, SPI

gate_json = 'config.json'

check_flag = 1
check_over_flag = False

check_id = ''
check_mac = ''

status = {}
lock_status_list = [] 

spi = SPI(baudrate=5000, polarity=0, phase=0, sck=Pin(16), mosi=Pin(14), miso=Pin(12),bits=8)
cs_pin = Pin(13,Pin.OUT)
r_pin = Pin(5,Pin.IN)

# 上报单个设备的状态
def reportStatu(mesg):
	global check_id, status, check_flag, lock_status_list, check_over_flag
	if check_over_flag:
		tm = time.localtime()
		lock_status = {"gateway_id": status['gateway_id'], "lock_list": lock_status_list, "datetime": tm}
		mesg = '{{"type": 2, "cmd": "reportStatusCompleted", "data": "{}"}}'
		check_flag = 1
		check_over_flag = False
		del lock_status_list
		return mesg.format(lock_status)
		
	if mesg[1:4] == '401':
		lock_statu = 'IdError'
		lock_eq = '999mA'
	else:
		lock_statu = mesg[5:7] if mesg[1:4] == '202' else '0'
		lock_eq = (str(int('0x' + mesg[7:11])) + 'mA') if mesg [1:4] == '202' else '0mA'
	lock_status_list.append({'lock_id': check_id, 'lock_statu': lock_statu, 'lock_eq': lock_eq})
	check_flag = 1
	return 1
# 上报密码
def reportPasswd(mesg):
	global status
	tm = time.localtime()
	passwd = mesg[5: 11]
	report = '{{"type": 3, "cmd": "{}", "data": "{}"}}'
	data = {"datetime": tm, "password": passwd, "gateway_id": status['gateway_id']}
	return report.format("CuserStorage", data)
# 发送重启命令
def restart(data):
	global status
	tm = time.localtime()
	send('#3#000#@')
	data = {"datetime": tm, "gateway_id": status['gateway_id'], 'gateway_power': status['gateway_power']}
	mesg = '{{"type": 2, "cmd": "DevRestartSucess", "data": "{}"}}'
	return mesg.format(data)
# 更新网关自身电量
def updateGatePower(mesg):
	global status
	tm = time.localtime()
	with open("config.json","w") as dump_f:
		ujson.dump(status, dump_f)
	status['gateway_power'] = mesg.split('#')[2]
	data = {"datetime": tm, "gateway_id": status['gateway_id'], 'gateway_power': status['gateway_power']}
	msg = '{{"type": 3, "cmd": "updateGatewayPower", "data": "{}"}}'.format(data)
	return msg
	# return 1
# 向51发送指令
def send(data) :
	# print(data)
	cs_pin.value(0)
	spi.write(bytearray(data.encode("utf-8")))
	cs_pin.value(1)
# 读取51指令
def read(client, topic):
	cs_pin.value(0)
	buf = bytearray(26)
	spi.readinto(buf) 
	cs_pin.value(1)
	# print(str(buf, 'utf8'))
	if buf[0] == 35:
		responseKeyword(client, topic, str(buf,'utf8'))
# 向51发送指令, 扫描列表锁状态的状态
def checkLockEQStatus(data):
	if data['data']['lock_list'] == []:
		return -1
	global check_flag, check_id, check_over_flag
	for lock_id in data['data']['lock_list']:
		while True:
			if check_flag:
				check_id = lock_id
				send("#3#271#{}#@".format(check_id))
				check_flag = 0
				break
	del data
	check_over_flag = True
	return 1
# 初始化SPI
def monitorKeyboard(client, topic):
	global status
	def funv(v):
		read(client, topic)
	cs_pin.value(1)
	r_pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING , handler=funv)
	with open("config.json",'r') as load_f:
		status = ujson.load(load_f)
# 锁操作, 开关
def lock_oem(data):
	global check_mac
	# 开锁、关锁、开锁后关锁
	lock_ins = {'Sunlock': '0', 'Slock': '1', 'Sdlock': '2'}
	check_mac = data['data']['lock_mac']
	if check_mac == '':
		return -1
	send('#{}#270#{}#@'.format(lock_ins[data['cmd']], ''.join(data['data']['lock_mac'].split(":"))))
	return 1
# 密码错误 通知51
def passwdErr(data):
	# 指令冲突 待更改成250
	send('#3#249#@')
	return 1
# 更新时间
def updateTime(data):
	tm = tuple(data["data"]["server_time"])
	machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3] + 8, tm[4], tm[5], 0))
	return 1
# 处理键盘设备传输的指令
def responseKeyword(client, topic, mesg):
	global check_flag, status, check_mac
	report = ''
	tm = time.localtime()
	ble_ins = {'000': 'keybr_reset',
	'001': updateGatePower,
	'197': 'lock_bad',
	'200': 'lock_sucessed',
	'201': 'unlock_sucessed',
	'202': reportStatu,
	'203': 'dlock_successed',
	'290': reportPasswd,
	'400': reportStatu,
	'401': reportStatu
	}
	if mesg[1:4] == '000':
		check_flag = 1
	if type(ble_ins[mesg[1:4]]) == type('str'):
		report = '{{"type": 2, "cmd": "{}", "data": "{}"}}'
		data = {"datetime": tm, "lock_mac": check_mac, "gateway_id": status['gateway_id']}
		report = report.format(ble_ins[mesg[1:4]], data)
	else:
		report = ble_ins[mesg[1:4]](mesg)
		if  report == 1:
			return 
	client.publish(topic, report)
# 根据Odoo后台下发指令进行操作
def selectFunction(client, topic, data):
	func_dict = {
	"Sunlock": lock_oem,
	"Slock": lock_oem,
	"Sdlock": lock_oem,
	'SpasswdErr': passwdErr,
	'ScheckStatus': checkLockEQStatus,
	'SupdateTime': updateTime,
	'Srestart': restart,
	'over': 'over'
	}
	mesg = '{{"type": 2, "cmd": "{}", "data": {{"gateway_id": {}}}}}'
	if type(func_dict[data['cmd']]) == type('str'):
		# mesg = mesg.format("over", status['gateway_id'])
		# 结束通知
		# client.publish(topic, mesg)
		return 
	if data['cmd'] not in func_dict.keys():
		mesg = mesg.format("cmdNotFind", status['gateway_id'])
		client.publish(topic, mesg)
		return 
	result = func_dict.get(data["cmd"])(data)
	if result == 1:
		return 
		# mesg = mesg.format("success", status['gateway_id'])
	elif result == -1:
		return 
		# mesg = mesg.format("failed", status['gateway_id'])
	else:
		mesg = result
		client.publish(topic, mesg)
		return