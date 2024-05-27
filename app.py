import multiprocessing
import os

import dotenv
from telegram.ext import ApplicationBuilder

from utils import my_logging, bot_util

dotenv.load_dotenv(override=True)

logger = my_logging.get_logger('app')

# 获取 bots 目录下的所有子目录
bot_directories = [d for d in os.listdir('bots') if os.path.isdir(os.path.join('bots', d))]


def start_bot(bot_name, token, command_handlers=None):
	if token is None:
		logger.error("请先设置BOT TOKEN!")
	
	application = ApplicationBuilder() \
		.token(token) \
		.concurrent_updates(True) \
		.get_updates_read_timeout(60) \
		.get_updates_write_timeout(60) \
		.get_updates_connect_timeout(60) \
		.build()
	
	application.add_handlers(command_handlers)
	application.add_error_handler(bot_util.error_handler)
	
	logger.info(f"{bot_name} is started!!")
	application.run_polling(drop_pending_updates=True)


processes = []
# 动态加载每个机器人
for bot_directory in bot_directories:
	try:
		# 动态导入每个机器人的处理器 同时指明了需要导入的属性(函数,子模块等)
		bot_module = __import__(f'bots.{bot_directory}.bot', fromlist=['handlers'])
		
		handlers = getattr(bot_module, 'handlers')
		
		# todo 如果模块是dogyun 则还要添加定时任务
		if bot_directory == 'dogyun_bot':
			pass
		
		token = os.getenv(f'{bot_directory.upper()}_TOKEN')
		if token is None:
			logger.error(f'{bot_directory.upper()}_TOKEN未设置!')
		
		command_handlers = handlers()
		if bot_directory == 'tmdb_bot':
			p = multiprocessing.Process(target=start_bot, args=(bot_directory, token, command_handlers))
			processes.append(p)
	except ImportError as e:
		print(f"Failed to import bot {bot_directory}: {e}")

if __name__ == '__main__':
	for p in processes:
		p.start()
	for p in processes:
		p.join()
