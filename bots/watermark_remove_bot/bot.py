from telegram import Update
from telegram.ext import MessageHandler, CallbackContext, filters

from my_utils import my_logging

# 获取日志
logger = my_logging.get_logger('watermark_remove_bot')


async def default_handler(update: Update, context: CallbackContext):
	await update.message.reply_text(update.message.text)


def handlers():
	return [MessageHandler(filters=filters.ALL, callback=default_handler)]
