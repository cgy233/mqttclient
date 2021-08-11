import pyautogui
import json
import time

time.sleep(5)

mac_list = ['CB6AE6F785A1', 'C764505B2C15', 'EF02423D916A', 'E5DFC975A595', 'E444388EAD70']
# ins_list = ['Sunlock', 'Slock', 'Sdlock']
ins_list = ['Sdlock']

pyautogui.FAILSAFE = False

pyautogui.PAUSE = 1
tick = 0

pyautogui.click(x=860, y=580)
pyautogui.hotkey('ctrl', 'a')
pyautogui.press('backspace')

while tick <=100:
	for ins in ins_list:
		for mac in mac_list:
			mesg = {"type": 1, "cmd": ins, "data": {"lock_mac": mac}}
			# print(json.dumps(mesg))
			pyautogui.typewrite(json.dumps(mesg))
			pyautogui.click(x=444, y=684)
			pyautogui.click(x=860, y=580)
			pyautogui.hotkey('ctrl', 'a')
			pyautogui.press('backspace')
			pyautogui.typewrite(f'Tick: {tick}\nTest ins: {ins}\nTest mac: {mac}')
			time.sleep(15)
			pyautogui.hotkey('ctrl', 'a')
			pyautogui.press('backspace')
	tick += 1
