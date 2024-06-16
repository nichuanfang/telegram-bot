import asyncio
import functools
import re
import uuid

import openai
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from bots.gpt_bot.chat import Chat
from my_utils.my_logging import get_logger
from my_utils.validation_util import validate

logger = get_logger('bot_util')
values = validate('ALLOWED_TELEGRAM_USER_IDS', 'FREE_OPENAI_API_KEY', 'FREE_OPENAI_BASE_URL')
# 允许访问的用户列表 逗号分割并去除空格
ALLOWED_TELEGRAM_USER_IDS = [user_id.strip() for user_id in values[0].split(',')]
# 免费的api-key
FREE_OPENAI_API_KEY = values[1]
# 免费的base_url
FREE_OPENAI_BASE_URL = values[2]


def auth(func):
	"""
	自定义授权装饰器
	Args:
		func: 需要授权的方法

	Returns:

	"""
	
	@functools.wraps(func)
	async def wrapper(*args, **kwargs):
		# 获取update和context
		update: Update = args[0]
		context: CallbackContext = args[1]
		user_id = update.effective_user.id
		if str(user_id) not in ALLOWED_TELEGRAM_USER_IDS:
			# 只针对GBTBot开放访问 其他机器人正常拦截
			if context.bot.first_name == 'GPTBot':
				logger.info(f'=================user {user_id} access the GPTbot for free===================')
				if 'chat' not in context.user_data:
					chat_init_params = {
						"api_key": FREE_OPENAI_API_KEY,
						"base_url": FREE_OPENAI_BASE_URL,
						"max_retries": openai.DEFAULT_MAX_RETRIES,
						"timeout": openai.DEFAULT_TIMEOUT,
						"msg_max_count": 5,
						"is_free": True
					}
					context.user_data['chat'] = Chat(**chat_init_params)
			else:
				logger.warn(f"======================user {user_id}'s  access has been filtered====================")
				await update.message.reply_text('You are not authorized to use this bot.')
				return
		await func(*args, **kwargs)
	
	return wrapper


async def uuid_generator():
	while True:
		yield uuid.uuid4().__str__()


async def coroutine_wrapper(normal_function, *args, **kwargs):
	return await asyncio.to_thread(normal_function, *args, **kwargs)


async def async_func(normal_function, *args, **kwargs):
	return await coroutine_wrapper(normal_function, *args, **kwargs)


async def send_typing_action(update: Update, context: CallbackContext, flag_key):
	while context.user_data.get(flag_key, False):
		await update.message.reply_chat_action(action='typing')
		await asyncio.sleep(2)  # 每2秒发送一次 typing 状态


async def send_message(update: Update, text):
	try:
		escaped_text = escape_markdown_v2(text)  # 转义特殊字符
		return await update.message.reply_text(escaped_text,
		                                       reply_to_message_id=update.message.message_id,
		                                       disable_web_page_preview=True,
		                                       parse_mode=ParseMode.MARKDOWN_V2)
	except:
		return await update.message.reply_text(text, reply_to_message_id=update.message.message_id,
		                                       disable_web_page_preview=True)


async def edit_message(update: Update, context: CallbackContext, message_id, stream_ended, text):
	try:
		# 等流式响应完全结束再尝试markdown格式 加快速度
		if stream_ended:
			escaped_text = escape_markdown_v2(text)
			await context.bot.edit_message_text(
				text=escaped_text,
				chat_id=update.message.chat_id,
				message_id=message_id,
				disable_web_page_preview=True,
				parse_mode=ParseMode.MARKDOWN_V2
			)
		else:
			await context.bot.edit_message_text(
				text=text,
				chat_id=update.message.chat_id,
				message_id=message_id,
				disable_web_page_preview=True
			)
	except Exception:
		try:
			await context.bot.edit_message_text(
				text=text,
				chat_id=update.message.chat_id,
				message_id=message_id, disable_web_page_preview=True)
		except Exception:
			pass


def escape_markdown_v2(text: str) -> str:
	"""
	Escape special characters for Telegram MarkdownV2 and replace every pair of consecutive asterisks (**) with a single asterisk (*).
	"""
	try:
		escape_chars = r"\_[]()#~>+-=|{}.!"
		escaped_text = re.sub(f"([{re.escape(escape_chars)}])", r'\\\1', text)
		escaped_text = re.sub(r'\\\*\\\*', '**', escaped_text)
		return escaped_text
	except Exception as e:
		return str(e)
