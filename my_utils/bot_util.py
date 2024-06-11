import asyncio
import re
import time

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext


async def coroutine_wrapper(normal_function, *args, **kwargs):
	return await asyncio.to_thread(normal_function, *args, **kwargs)


async def async_func(normal_function, *args, **kwargs):
	return await coroutine_wrapper(normal_function, *args, **kwargs)


async def send_typing_action(update: Update, context: CallbackContext, flag_key):
	while context.user_data.get(flag_key, False):
		await update.message.reply_chat_action(action='typing')
		await asyncio.sleep(2)  # 每2秒发送一次 typing 状态


def escape_markdown_v2(text: str) -> str:
	"""
	Escape special characters for Telegram MarkdownV2 and replace every pair of consecutive asterisks (**) with a single asterisk (*).
	"""
	try:
		return re.sub(f"([{re.escape(r'_[]()~>#+-=|{}.!')}])", r'\\\1', text.replace('**', '*'))
	except Exception as e:
		return e
