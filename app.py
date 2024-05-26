import asyncio
import os
import threading

import dotenv
from telegram.ext import ApplicationBuilder

from utils import my_logging

dotenv.load_dotenv()

logger = my_logging.get_logger('app')

# 获取 bots 目录下的所有子目录
bot_directories = [d for d in os.listdir('bots') if os.path.isdir(os.path.join('bots', d))]


def start_bot(bot_name, token, handlers=None):
	logger.info(f"Starting  {bot_name} ...")
	
	if token is None:
		logger.error("请先设置BOT TOKEN!")
	
	application = ApplicationBuilder() \
		.token(token) \
		.build()
	# application.add_handler(CommandHandler('reset', ))
	# application.add_handler(CommandHandler('help', ))
	# application.add_error_handler(error_handler)
	
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	logger.info(f"{bot_name} is started!!")
	loop.run_until_complete(application.run_polling())


threads = []
# 动态加载每个机器人
for bot_directory in bot_directories:
	try:
		# 动态导入每个机器人的处理器 同时指明了需要导入的属性(函数,子模块等)
		bot_module = __import__(f'bots.{bot_directory}.bot', fromlist=['start_bot'])
		
		# todo 如果模块是dogyun 则还要添加定时任务
		if bot_directory == 'dogyun_bot':
			pass
		
		token = os.getenv(f'{bot_directory.upper()}_TOKEN')
		if token is None:
			logger.error(f'{bot_directory.upper()}_TOKEN未设置!')
		
		threads.append(
			threading.Thread(target=start_bot, kwargs={'bot_name': bot_directory, 'token': token, 'handlers': None}))
	except ImportError as e:
		print(f"Failed to import bot {bot_directory}: {e}")

if __name__ == '__main__':
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join()
