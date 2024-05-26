import subprocess
from datetime import date

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from utils import my_logging
from utils.validation_util import validate

# 获取日志
logger = my_logging.get_logger('dogyun_bot')

values = validate('DOGYUN_BOT_SERVER_ID', 'DOGYUN_BOT_CSRF_TOKEN', 'DOGYUN_BOT_COOKIE')

DOGYUN_BOT_SERVER_ID = values[0]
DOGYUN_BOT_CSRF_TOKEN = values[1]
DOGYUN_BOT_COOKIE = values[2]


async def get_server_status(update: Update, context: CallbackContext):
	"""获取服务器状态

	Returns:
		_type_: _description_
	"""
	url = f'https://cvm.dogyun.com/server/{DOGYUN_BOT_SERVER_ID}'
	headers = {
		'X-Csrf-Token': DOGYUN_BOT_CSRF_TOKEN,
		'Origin': 'https://vm.dogyun.com',
		'Referer': 'https://vm.dogyun.com',
		'Cookie': DOGYUN_BOT_COOKIE
	}
	try:
		# 发送post请求
		response = requests.get(url, headers=headers, verify=True)
		if response.url == 'https://account.dogyun.com/login':
			# tg通知dogyun cookie已过期
			await update.message.reply_text(
				'dogyun cookie已过期,请更新cookie!')
			return
	except Exception as e:
		logger.error(e)
		return
	try:
		soup = BeautifulSoup(response.text, 'lxml')
		# cpu
		cpu = soup.find_all('div', class_='d-flex justify-content-between')[0].contents[1].contents[0]
		# 内存
		mem = soup.find_all('div', class_='d-flex justify-content-between')[1].contents[1].next
		# 本日流量
		curr_day_throughput = soup.find_all('span', class_='text-primary')[1].text
		# 本月流量
		curr_month_throughput = soup.find_all('span', class_='text-primary')[3].text
		# 剩余流量
		# rest_throughput = str(float(soup.find_all('div', class_='d-flex justify-content-between')[2].contents[3].next.split('/')[1].split(' ')[1]) - float(soup.find_all('div', class_='d-flex justify-content-between')[2].contents[3].next.split('/')[0].split(' ')[0])) + ' GB'
		# 重置时间
		# reset_time = soup.find_all('div', class_='d-flex justify-content-between')[2].contents[1].contents[1].text.split(' ')[0]
		
		status_message = f'CPU: {cpu}\n内存: {mem}\n本日流量: {curr_day_throughput}\n本月流量: {curr_month_throughput}'
		await update.message.reply_text(status_message)
	except Exception as e:
		await update.message.reply_text(f'获取服务器状态失败: {e}')


# @bot.message_handler(commands=['draw_lottery'])
async def draw_lottery(update: Update, context: CallbackContext):
	"""抽奖

	Args:
		message (_type_): _description_
	"""
	url = f'https://console.dogyun.com/turntable/lottery'
	headers = {
		'X-Csrf-Token': DOGYUN_BOT_CSRF_TOKEN,
		'Origin': 'https://cvm.dogyun.com',
		'Referer': 'https://console.dogyun.com/turntable',
		'Cookie': DOGYUN_BOT_COOKIE
	}
	# 发送put请求
	try:
		response = requests.put(url, headers=headers, verify=True)
		if response.url == 'https://account.dogyun.com/login':
			# tg通知dogyun cookie已过期
			await update.message.reply_text('dogyun cookie已过期,请更新cookie!')
		data = response.json()
	except Exception as e:
		logger.error(e)
		return
	# 获取抽奖结果
	try:
		result = data['success']
	except:
		await update.message.reply_text('目前没有抽奖活动')
		return
	if result:
		# 查看奖品
		prize_url = f'https://console.dogyun.com/turntable/prize/page'
		prize_body = {"draw": 2, "columns": [{"data": "prizeName", "name": "", "searchable": True, "orderable": False,
		                                      "search": {"value": "", "regex": False}},
		                                     {"data": "status", "name": "", "searchable": True, "orderable": False,
		                                      "search": {
			                                      "value": "", "regex": False}},
		                                     {"data": "createTime", "name": "", "searchable": True, "orderable": True,
		                                      "search": {
			                                      "value": "", "regex": False}},
		                                     {"data": "descr", "name": "", "searchable": True, "orderable": False,
		                                      "search": {"value": "", "regex": False}}],
		              "order": [{"column": 2, "dir": "desc"}], "start": 0, "length": 10,
		              "search": {"value": "", "regex": False}}
		# post请求
		try:
			prize_response = requests.post(
				prize_url, json=prize_body, headers=headers, verify=True)
		except Exception as e:
			await update.message.reply_text(f'查看奖品失败: {e.args[0]}')
			return
		# 获取返回的json数据
		try:
			prize_data = prize_response.json()
		except:
			# tg通知dogyun cookie已过期
			await update.message.reply_text('dogyun cookie已过期,请更新cookie')
			return
		# 获取奖品信息
		prize_infos: list = prize_data['data']
		
		if len(prize_infos) > 0 and prize_infos[0]['createTime'].split(' ')[0] == date.today().strftime("%Y-%m-%d"):
			await update.message.reply_text(
				f'抽奖结果: 成功\n奖品: {prize_infos[0]["prizeName"]}\n状态: {prize_infos[0]["status"]}\n描述: {prize_infos[0]["descr"]}')
	else:
		await update.message.reply_text(f'抽奖失败: {data["message"]}')


async def bitwarden_backup(update: Update, context: CallbackContext):
	"""备份bitwarden

	Args:
		message (_type_): _description_
	"""
	script = 'curl -s https://raw.githubusercontent.com/nichuanfang/config-server/master/linux/bash/step2/vps/backup_bitwarden.sh | bash'
	# try:
	#     ssd_fd = ssh_connect(vps_config["VPS_HOST"], vps_config["VPS_PORT"],
	#                          vps_config["VPS_USER"], vps_config["VPS_PASS"])
	# except:
	#     bot.reply_to(message, f'无法连接到服务器{vps_config["VPS_HOST"]}')
	#     return
	try:
		subprocess.call(
			f'nsenter -m -u -i -n -p -t 1 bash -c "{script}"', shell=True)
	except:
		await update.message.reply_text('执行脚本报错')
		return
	await update.message.reply_text('备份bitwarden成功')

async def exec_cmd(update: Update, context: CallbackContext):
	"""执行bash脚本

	Args:
		message (_type_): _description_
	"""
	message_text = update.message.text
	if message_text.strip() == '/exec_cmd':
		await update.message.reply_text('请输入命令!')
		return
	script = message_text[10:].strip()
	if script in ['systemctl stop tgbot', 'systemctl restart tgbot', 'reboot']:
		await update.message.reply_text('禁止执行该命令')
		return
	# try:
	#     ssd_fd = ssh_connect(vps_config["VPS_HOST"], vps_config["VPS_PORT"],
	#                          vps_config["VPS_USER"], vps_config["VPS_PASS"])
	# except:
	#     bot.reply_to(message, f'无法连接到服务器{vps_config["VPS_HOST"]}')
	#     return
	try:
		subprocess.call(
			f'nsenter -m -u -i -n -p -t 1 bash -c "{script}"', shell=True)
	except:
		await update.message.reply_text('执行命令报错')
		return
	await update.message.reply_text('执行命令成功')
	

def handlers():
	return [CommandHandler('server_info', get_server_status),
	        CommandHandler('draw_lottery', draw_lottery),
	        CommandHandler('bitwarden_backup', bitwarden_backup),
	        CommandHandler('exec_cmd',exec_cmd)]
