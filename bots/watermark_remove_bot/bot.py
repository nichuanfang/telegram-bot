import asyncio

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import MessageHandler, CallbackContext, filters, CommandHandler

from bots.watermark_remove_bot.uu_mvp_http_request import UuMvpHttpRequest
from my_utils import my_logging, bot_util

# 获取日志
logger = my_logging.get_logger('watermark_remove_bot')


async def start(update: Update, context: CallbackContext) -> None:
	start_message = (
		"欢迎使用*万能去水印*\!\n\n输入常见社交平台的*url*获取无水印图片\~"
	)
	await update.message.reply_text(start_message, parse_mode=ParseMode.MARKDOWN_V2)


async def watermark_remove_uumvp(update: Update, context: CallbackContext):
	"""
	使用uumvp平台进行图片去水印
	Args:
		update:  更新对象
		context:  上下文
	"""
	await bot_util.send_typing(update)
	try:
		req = UuMvpHttpRequest()
		response = await req.query(update.message.text)
		if response['code'] == 100:
			pics = response['data']['pics']
			for pic in pics:
				await update.message.reply_photo(pic, reply_to_message_id=update.message.message_id)
		else:
			await update.message.reply_text(f'{update.message.text}解析失败!')
	except Exception:
		await update.message.reply_text(f'{update.message.text}解析失败')


async def default_handler(update: Update, context: CallbackContext):
	await watermark_remove_uumvp(update, context)


def handlers():
	return [CommandHandler('start', start),
	        MessageHandler(filters=filters.TEXT, callback=default_handler)]
