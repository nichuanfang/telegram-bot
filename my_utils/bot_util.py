import asyncio
import functools
import re
import uuid

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from my_utils.my_logging import get_logger
from my_utils.validation_util import validate

logger = get_logger('bot_util')
values = validate('ALLOWED_TELEGRAM_USER_IDS')
# 允许访问的用户列表 逗号分割并去除空格
ALLOWED_TELEGRAM_USER_IDS = [user_id.strip() for user_id in values[0].split(',')]


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
		user_id = update.effective_user.id
		if str(user_id) not in ALLOWED_TELEGRAM_USER_IDS:
			logger.warn(f'user {user_id} has been filtered!')
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
		                                       parse_mode=ParseMode.MARKDOWN_V2)
	except:
		return await update.message.reply_text(text, reply_to_message_id=update.message.message_id)


async def edit_message(update: Update, context: CallbackContext, message_id, stream_ended, text):
	try:
		# 等流式响应完全结束再尝试markdown格式 加快速度
		if stream_ended:
			escaped_text = escape_markdown_v2(text)  # 转义特殊字符
			await context.bot.edit_message_text(text=escaped_text, chat_id=update.message.chat_id,
			                                    message_id=message_id,
			                                    parse_mode=ParseMode.MARKDOWN_V2)
		else:
			await context.bot.edit_message_text(text=text, chat_id=update.message.chat_id, message_id=message_id)
	except:
		await context.bot.edit_message_text(text=text, chat_id=update.message.chat_id, message_id=message_id)


def escape_markdown_v2(text: str) -> str:
	"""
	Escape special characters for Telegram MarkdownV2 and replace every pair of consecutive asterisks (**) with a single asterisk (*).
	"""
	try:
		# List of characters that need to be escaped in MarkdownV2
		escape_chars = r'_[]()~>#+-=|{}.!'
		# Escape each character
		escaped_text = re.sub(f"([{re.escape(escape_chars)}])", r'\\\1', text)
		# Replace every pair of consecutive asterisks (**) with a single asterisk (*)
		escaped_text = escaped_text.replace('**', '*')
		return escaped_text
	except Exception as e:
		return str(e)
