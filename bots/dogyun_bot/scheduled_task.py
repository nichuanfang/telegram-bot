import os

from bs4 import BeautifulSoup

from utils import my_logging

# 获取日志
logger = my_logging.get_logger('dogyun_bot')

DOGYUN_BOT_SERVER_ID = os.environ.get('DOGYUN_BOT_SERVER_ID')
DOGYUN_BOT_CSRF_TOKEN = os.environ.get('DOGYUN_BOT_CSRF_TOKEN')
DOGYUN_BOT_COOKIE = os.environ.get('DOGYUN_BOT_COOKIE')
DOGYUN_BOT_CHAT_ID = os.environ.get('DOGYUN_BOT_CHAT_ID')


# 每月7号
def get_traffic_packet():
	"""自动领取流量包
	"""
	url = f'https://cvm.dogyun.com/traffic/package/level'
	headers = {
		'X-Csrf-Token': dogyun_config['DOGYUN_CSRF_TOKEN'],
		'Origin': 'https://cvm.dogyun.com',
		'Referer': 'https://cvm.dogyun.com/traffic/package/list',
		'Cookie': dogyun_config['DOGYUN_COOKIE']
	}
	try:
		# 发送post请求
		response = requests.post(url, headers=headers, verify=True)
		if response.url == 'https://account.dogyun.com/login':
			# tg通知dogyun cookie已过期
			bot.send_message(
				dogyun_config['CHAT_ID'], 'dogyun cookie已过期,请更新cookie! \n https://github.com/nichuanfang/tgbot/edit/main/settings/config.py')
			return
		data = response.json()
	except Exception as e:
		logger.error(e)
		return
	# 获取领取结果
	result = data['message']
	# 获取当前时间
	now = datetime.now()
	# 获取当前日期
	today = date.today()
	# 获取当前时间
	current_time = now.strftime("%H:%M:%S")
	# 获取当前日期
	current_date = today.strftime("%Y-%m-%d")
	# 记录日志
	logger.info(f'{current_date} {current_time} {result}')
	# 发送通知
	bot.send_message(dogyun_config['CHAT_ID'], f'等级奖励通用流量包: {result}')


def lucky_draw_notice():
	"""抽奖活动通知
	"""
	url = f'https://console.dogyun.com/turntable'
	headers = {
		'Cookie': dogyun_config['DOGYUN_COOKIE'],
		'Referer': 'https://member.dogyun.com/',
		'Origin': 'https://console.dogyun.com',
		'X-Csrf-Token': dogyun_config['DOGYUN_CSRF_TOKEN']
	}
	try:
		# 发起get请求
		response = requests.get(url, headers=headers, verify=True)
		if response.url == 'https://account.dogyun.com/login':
			# tg通知dogyun cookie已过期
			bot.send_message(
				dogyun_config['CHAT_ID'], 'dogyun cookie已过期,请更新cookie! \n https://github.com/nichuanfang/tgbot/edit/main/settings/config.py')
			return
	except Exception as e:
		logger.error(e)
		return
	soup = BeautifulSoup(response.text, 'lxml')
	try:
		result = soup.find('a', class_='gb-turntable-btn').text
		bot.send_message(dogyun_config['CHAT_ID'],
		                 f'抽奖活动通知: {soup.find("strong").text}')
		logger.info(f'抽奖活动通知: {soup.find("strong").text}')
	except:
		# '暂无抽奖活动'
		pass


# 余额不足提醒
def balance_lack_notice():
	"""余额不足提醒
	"""
	url = f'https://console.dogyun.com'
	headers = {
		'Cookie': dogyun_config['DOGYUN_COOKIE'],
		'Referer': 'https://member.dogyun.com/',
		'Origin': 'https://console.dogyun.com',
		'X-Csrf-Token': dogyun_config['DOGYUN_CSRF_TOKEN']
	}
	try:
		# 发起get请求
		response = requests.get(url, headers=headers, verify=True)
		if response.url == 'https://account.dogyun.com/login':
			# tg通知dogyun cookie已过期
			bot.send_message(
				dogyun_config['CHAT_ID'], 'dogyun cookie已过期,请更新cookie! \n https://github.com/nichuanfang/tgbot/edit/main/settings/config.py')
			return
	except Exception as e:
		logger.error(e)
		return
	soup = BeautifulSoup(response.text, 'lxml')
	try:
		result = soup.find('span', class_='h5 font-weight-normal').text
		# 根据正则表达式提取数字
		balance = re.findall(r"\d+\.?\d*", result)[0]
		if float(balance) < 10:
			bot.send_message(dogyun_config['CHAT_ID'], f'余额不足提醒: {balance}元')
			logger.info(f'余额不足提醒: {balance}元')
	except:
		pass