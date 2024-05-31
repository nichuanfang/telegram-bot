import asyncio

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from my_utils import my_logging, bot_util
from my_utils.github_util import trigger_github_workflow

# 获取日志
logger = my_logging.get_logger('github_workflow_bot')


# 从 Update 中可以拿到消息的类型、具体内容、发送者等关键信息，从 CallbackContext 中可以获取机器人本身的一些信息等。在使用 \ 开头的对应命令后就能进入到对应的方法，也可以对此进行类封装
async def scrape_metadata(update: Update, context: CallbackContext):
	"""刮削影视元信息

	Returns:
		_type_: _description_
	"""
	typing_task = asyncio.create_task(bot_util.send_typing_action(update))
	try:
		await asyncio.gather(bot_util.async_func(trigger_github_workflow,'movie-tvshow-spider', 'crawl movies and shows'))
	except Exception as e:
		typing_task.cancel()
		await update.message.reply_text(e)
		return 
	logger.info('Scraped!')
	typing_task.cancel()
	await update.message.reply_text('已触发工作流: 刮削影视元信息,查看刮削日志: https://github.com/nichuanfang/movie-tvshow-spider/actions')

def handlers():
	return [CommandHandler('scrape_metadata', scrape_metadata)]
