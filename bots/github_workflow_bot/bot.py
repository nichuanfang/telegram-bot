import asyncio

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from my_utils import my_logging, bot_util
from my_utils.bot_util import auth
from my_utils.github_util import trigger_github_workflow

# 获取日志
logger = my_logging.get_logger('github_workflow_bot')

@auth
async def scrape_metadata(update: Update, context: CallbackContext):
	"""刮削影视元信息

	Returns:
		_type_: _description_
	"""
	flag_key = update.message.message_id
	# 启动一个异步任务来发送 typing 状态
	context.user_data[flag_key] = True
	typing_task = asyncio.create_task(bot_util.send_typing_action(update, context, flag_key))
	try:
		await asyncio.gather(
			bot_util.async_func(trigger_github_workflow, 'movie-tvshow-spider', 'crawl movies and shows'))
	except Exception as e:
		try:
			context.user_data[flag_key] = False
			await update.message.reply_text(e, reply_to_message_id=update.message.message_id)
		finally:
			await typing_task
		return
	logger.info('Scraped!')
	try:
		context.user_data[flag_key] = False
		await update.message.reply_text(
			'已触发工作流: 刮削影视元信息,查看刮削日志: https://github.com/nichuanfang/movie-tvshow-spider/actions',
			reply_to_message_id=update.message.message_id)
	finally:
		await typing_task


def handlers():
	return [CommandHandler('scrape_metadata', scrape_metadata)]
