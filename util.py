import ujson
import gc
import time
import machine
from machine import Pin, SPI

class Util():
	def __init__(self):
	    self.gateway_id = ''
	    self.check_id = ''
	    self.check_mac = ''
	    self.check_flag = 1
	    self.check_over_flag = False
	    self.lock_status_list = [] 
	    self.spi = SPI(baudrate=5000, polarity=0, phase=0, sck=Pin(16), mosi=Pin(14), miso=Pin(12),bits=8)
	    self.cs_pin = Pin(13,Pin.OUT)
	    self.r_pin = Pin(5,Pin.IN)

	# 上报单个设备的状态
	def reportStatu(self, mesg):
		# 搜索完成 上报所有锁的电量
		if self.check_over_flag:
			tm = time.localtime()
			self.check_flag = 1
			self.check_over_flag = False
			# 自动化测试 51按键
			self.send('#3#003#@')
			return '{{"cmd": "RSC", "data": "{}"}}' \
				.format({"gateway_id": self.gateway_id, "lock_list": self.lock_status_list, "datetime": tm})
		if mesg[1:4] == '401':
			lock_statu = 'IdError'
			lock_eq = '999mA'
		else:
			lock_statu = mesg[5:7] if mesg[1:4] == '202' else '0'
			lock_eq = (str(int('0x' + mesg[7:11])) + 'mA') if mesg [1:4] == '202' else '0mA'
			# l_i 锁id l_s 锁的物理状态
		self.lock_status_list.append({'l_i': self.check_id, 'l_s': lock_statu, 'l_e': lock_eq})
		self.check_flag = 1
		return 1
	# 上报密码
	def reportPasswd(self, mesg):
		tm = time.localtime()
		passwd = mesg[5: 11]
		report = '{{"cmd": "{}", "data": "{}"}}'
		data = {"datetime": tm, "password": passwd, "gateway_id": self.gateway_id}
		return report.format("CuserStorage", data)
	# 发送重启命令
	def restart(self, data):
		tm = time.localtime()
		self.send('#3#004#@')
		data = {"datetime": tm, "gateway_id": self.gateway_id}
		mesg = '{{"cmd": "DRS", "data": "{}"}}'
		return mesg.format(data)
	# 51重启ESP8266没有重启
	def normal_mode(self, data):
		if not self.check_over_flag:
			self.send('#3#003#@')
		return
	# 更新网关自身电量
	def updateGatePower(self, mesg):
		tm = time.localtime()
		power = mesg.split('#')[2]
		return '{{"cmd": "UGP", "data": "{}"}}' \
			.format({"datetime": tm, "gateway_id": self.gateway_id, 'gateway_power': power})

		# return 1
	# 向51发送指令
	def send(self, data) :
		print(data)
		self.cs_pin.value(0)
		self.spi.write(bytearray(data.encode("utf-8")))
		self.cs_pin.value(1)
	# 读取51指令
	def read(self, client, topic):
		self.cs_pin.value(0)
		buf = bytearray(26)
		self.spi.readinto(buf) 
		self.cs_pin.value(1)
		if buf[0] == 35:
			print(str(buf, 'utf8'))
			self.responseKeyword(client, topic, str(buf,'utf8'))
	# 向51发送指令, 扫描列表锁状态的状态
	def checkLockEQStatus(self, data):
		gc.collect()
		if data['data']['lock_list'] == []:
			return -1
		for lock_id in data['data']['lock_list']:
			while True:
				if self.check_flag:
					self.check_id = lock_id
					self.send("#3#271#{}#@".format(self.check_id))
					self.check_flag = 0
					break
		self.check_over_flag = True
		return 1
	# 初始化SPI
	def monitorKeyboard(self, client, topic, gateway_id):
		self.gateway_id = gateway_id
		def funv(v):
			self.read(client, topic)
		self.cs_pin.value(1)
		self.r_pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING , handler=funv)
	# 锁操作, 开关
	def lock_oem(self, data):
		# 开锁、关锁、开锁后关锁
		lock_ins = {'Sunlock': '0', 'Slock': '1', 'Sdlock': '2'}
		self.check_mac = data['data']['lock_mac']
		if self.check_mac == '':
			return -1
		self.send('#{}#270#{}#@' \
		.format(lock_ins[data['cmd']], ''.join(data['data']['lock_mac'].split(":"))))
		return 1
	# 密码错误 通知51
	def passwdErr(self, data):
		self.send('#3#250#@')
		return 1
	# 更新时间
	def updateTime(self, data):
		tm = tuple(data["data"]["server_time"])
		machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3] + 8, tm[4], tm[5], 0))
		return 1
	# 处理键盘设备传输的指令
	def responseKeyword(self, client, topic, mesg):
		report = ''
		tm = time.localtime()
		ble_ins = {'000': 'keybr_reset',
		'001': self.updateGatePower,
		'003': self.normal_mode,
		'197': 'lock_bad',
		'200': 'lock_sucessed',
		'201': 'unlock_sucessed',
		'202': self.reportStatu,
		'203': 'dlock_successed',
		'290': self.reportPasswd,
		'400': self.reportStatu,
		'401': self.reportStatu
		}
		if mesg[1:4] == '003':
			ble_ins[mesg[1:4]](mesg)
			return
		if mesg[1:4] == '000':
			self.check_flag = 1
			return
		if type(ble_ins[mesg[1:4]]) == type('str'):
			report = '{{"cmd": "{}", "data": "{}"}}' \
				.format(ble_ins[mesg[1:4]], {"datetime": tm, "lock_mac": self.check_mac, "gateway_id": self.gateway_id})
		else:
			report = ble_ins[mesg[1:4]](mesg)
			if report == 1:
				return 
		client.publish(topic, report)
		self.lock_status_list = []
	# 根据Odoo后台下发指令进行操作
	def selectFunction(self, client, topic, data):
		func_dict = {
		"Sunlock": self.lock_oem,
		"Slock": self.lock_oem,
		"Sdlock": self.lock_oem,
		'SpasswdErr': self.passwdErr,
		'ScheckStatus': self.checkLockEQStatus,
		'SupdateTime': self.updateTime,
		'Srestart': self.restart,
		'over': 'over'
		}
		mesg = '{{"cmd": "{}", "data": {{"gateway_id": {}}}}}'
		# 指令字典里面找不到命令
		if data['cmd'] not in func_dict.keys():
			# mesg = mesg.format("cmdNotFind", self.gateway_id)
			# client.publish(topic, mesg)
			return 
		if type(func_dict[data['cmd']]) == type('str'):
			# mesg = mesg.format("over", status['gateway_id'])
			# client.publish(topic, mesg)
			return 
		result = func_dict.get(data["cmd"])(data)
		# 收到指令是否马上回应 暂不回应
		if result == 1 or result == -1:
			# mesg = mesg.format("success", status['gateway_id'])
			# mesg = mesg.format("failed", status['gateway_id'])
			return 
		else:
			mesg = result
			client.publish(topic, mesg)
			return