import pyautogui
import json
import time

time.sleep(5)

# mac_list = ['CB6AE6F785A1', 'C764505B2C15', 'EF02423D916A', 'E5DFC975A595', 'E444388EAD70', 'C9050D38509C', 'CA1AAD27BEEF', 'F06E1ABCD8E1']
mac_list = ['CB6AE6F785A1', 'EF02423D916A', 'E5DFC975A595', 'E444388EAD70', 'C9050D38509C', 'CA1AAD27BEEF', 'F06E1ABCD8E1']
# ins_list = ['Sunlock', 'Slock', 'Sdlock']
ins_list = ['Sdlock']

pyautogui.FAILSAFE = False

pyautogui.PUSE = 1
tick = 0

# 自动化测试程序（腾讯云）
while True:
	# for ins in ins_list:
	for i in range(len(mac_list) - 1):
		# gate1
		pyautogui.click(x=456, y=633)
		pyautogui.hotkey('ctrl', 'a')
		pyautogui.press('backspace')
		# mesg = {"type": 1, "cmd": ins, "data": {"lock_mac": mac}}
		mesg = {"type": 1, "cmd": "Sdlock", "data": {"lock_mac": mac_list[i], "cmd": "Sdlock"}}
		pyautogui.typewrite(json.dumps(mesg))
		pyautogui.click(x=157, y=804)
		pyautogui.click(x=456, y=633)

		# gate2
		pyautogui.click(x=1434, y=678)
		pyautogui.hotkey('ctrl', 'a')
		pyautogui.press('backspace')
		mesg = {"type": 1, "cmd": "Sdlock", "data": {"lock_mac": mac_list[i+1], "cmd": "Sdlock"}}
		pyautogui.typewrite(json.dumps(mesg))
		pyautogui.click(x=1115, y=805)
		time.sleep(15)
	tick += 1
