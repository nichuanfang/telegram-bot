import asyncio
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext


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
		await update.message.reply_text(escaped_text,
		                                reply_to_message_id=update.message.message_id,
		                                parse_mode=ParseMode.MARKDOWN_V2)
	except:
		await update.message.reply_text(text, reply_to_message_id=update.message.message_id)


async def edit_message(update: Update, context: CallbackContext, message_id, text):
	try:
		escaped_text = escape_markdown_v2(text)  # 转义特殊字符
		await context.bot.edit_message_text(text=escaped_text, chat_id=update.message.chat_id, message_id=message_id,
		                                    parse_mode=ParseMode.MARKDOWN_V2)
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
