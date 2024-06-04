import asyncio

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import MessageHandler, CallbackContext, filters, CommandHandler

from bots.watermark_remove_bot.uu_mvp_http_request import UuMvpHttpRequest
from bots.watermark_remove_bot.wsppx_http_request import WsppxHttpRequest
from my_utils import my_logging, regex_util, bot_util

# 获取日志
logger = my_logging.get_logger('watermark_remove_bot')


async def start(update: Update, context: CallbackContext) -> None:
	start_message = (
		"欢迎使用*万能去水印*\!\n\n输入常见社交平台的*url*获取无水印图片\~"
	)
	await update.message.reply_text(start_message, parse_mode=ParseMode.MARKDOWN_V2)


async def watermark_remove_wsppx(update: Update, context: CallbackContext):
	"""
	使用wsppx平台进行图片去水印
	Args:
		update:  update对象
		context:  上下文
	"""
	typing_task = asyncio.create_task(bot_util.send_typing_action(update))
	url = update.message.text
	if regex_util.is_valid_url(url):
		try:
			req = WsppxHttpRequest()
			response = await req.parse(url)
			if response['success']:
				image_list = response['result']['image_list']
				# 回复获取到的图片
				for image in image_list:
					await update.message.reply_photo(image, reply_to_message_id=update.message.message_id)
				typing_task.cancel()
			else:
				# 尝试下一个平台
				await watermark_remove_uumvp(update, context, typing_task)
		
		except Exception as e:
			logger.error(e)
			await watermark_remove_uumvp(update, context, typing_task)
	else:
		await update.message.reply_text('请输入合法的url')
		typing_task.cancel()
		return


async def watermark_remove_uumvp(update: Update, context: CallbackContext, typing_task):
	"""
	使用uumvp平台进行图片去水印
	Args:
		update:  更新对象
		context:  上下文
	"""
	try:
		req = UuMvpHttpRequest()
		response = await req.query(update.message.text)
		if response['code'] == 100:
			pics = response['data']['pics']
			for pic in pics:
				await update.message.reply_photo(pic, reply_to_message_id=update.message.message_id)
			typing_task.cancel()
		else:
			await update.message.reply_text(f'{update.message.text}解析失败!')
			typing_task.cancel()
	
	except Exception as e:
		logger.error(e)
		await update.message.reply_text(f'{update.message.text}解析失败: \n\n {e}')
		typing_task.cancel()


async def default_handler(update: Update, context: CallbackContext):
	# 从wsppx获取去水印后的图片 如果接口不可用 则使用20kaka平台的接口
	await watermark_remove_wsppx(update, context)


def handlers():
	return [CommandHandler('start', start),
	        MessageHandler(filters=filters.ALL, callback=default_handler)]
