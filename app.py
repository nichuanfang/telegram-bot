import asyncio
import multiprocessing
import os
import platform

import aiocron
import dotenv

dotenv.load_dotenv(override=True)
from telegram import Bot
from telegram.ext import ApplicationBuilder, ContextTypes

from bots.dogyun_bot.scheduled_task import lucky_draw_notice, balance_lack_notice

from my_utils import my_logging, validation_util

logger = my_logging.get_logger('app')

# 获取 bots 目录下的所有子目录
bot_directories = [d for d in os.listdir('bots') if os.path.isdir(os.path.join('bots', d))]


async def add_scheduled_tasks(bot):
	@aiocron.crontab('0 0 7 * *')  # 每月7号
	async def get_traffic_packet():
		await get_traffic_packet(bot)
	
	@aiocron.crontab('0 9 * * *')  # 每天9点
	async def lucky_draw_task():
		await lucky_draw_notice(bot)
	
	@aiocron.crontab('0 9 * * *')  # 每天9点
	async def balance_lack_task():
		await balance_lack_notice(bot)


async def error_handler(_: object, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""
	Handles errors in the telegram-python-bot library.
	"""
	
	# todo 暂时测试webhook效果 需要查看错误日志 测试通过需要关闭!
	# if platform.system().lower() == 'windows':
	# 	logger.error(f'Exception while handling an update: {context.error}')


def start_bot(bot_name, token, command_handlers=None):
	if token is None:
		logger.error("请先设置BOT TOKEN!")
		return
	application = ApplicationBuilder() \
		.token(token) \
		.concurrent_updates(True) \
		.get_updates_read_timeout(60) \
		.get_updates_write_timeout(60) \
		.get_updates_connect_timeout(60) \
		.build()
	
	application.add_handlers(command_handlers)
	application.add_error_handler(error_handler)
	
	logger.info(f"{bot_name} is started!!")
	if platform.system().lower() == 'windows':
		application.run_polling(drop_pending_updates=True)
	else:
		validate_res = validation_util.validate(f'{bot_name.upper()}_WEBHOOK_URL', f'{bot_name.upper()}_WEBHOOK_PORT')
		webhook_url = validate_res[0]
		webhook_port = validate_res[1]
		application.run_webhook(
			listen="0.0.0.0",
			port=webhook_port,
			url_path=webhook_url,
			webhook_url=webhook_url,
		)


async def start_scheduler(token):
	bot = Bot(token=token)
	await add_scheduled_tasks(bot)
	logger.info("Scheduler started.")
	try:
		while True:
			await asyncio.sleep(1)
	except (KeyboardInterrupt, SystemExit):
		pass


def run_scheduler(token):
	asyncio.run(start_scheduler(token))


processes = []
# 动态加载每个机器人
for bot_directory in bot_directories:
	try:
		bot_module = __import__(f'bots.{bot_directory}.bot', fromlist=['handlers'])
		handlers = getattr(bot_module, 'handlers')
		
		token = os.getenv(f'{bot_directory.upper()}_TOKEN')
		if token is None or len(token) == 0:
			logger.error(f'{bot_directory.upper()}_TOKEN未设置!')
		
		if bot_directory == 'dogyun_bot':
			# 创建一个单独的进程来运行调度器
			p_scheduler = multiprocessing.Process(target=run_scheduler, args=(token,))
			processes.append(p_scheduler)
		
		command_handlers = handlers()
		p_bot = multiprocessing.Process(target=start_bot, args=(bot_directory, token, command_handlers))
		processes.append(p_bot)
	except ImportError as e:
		logger.error(f"Failed to import bot {bot_directory}: {e}")

if __name__ == '__main__':
	for p in processes:
		p.start()
	for p in processes:
		p.join()
