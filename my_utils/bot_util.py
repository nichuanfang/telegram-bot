import asyncio
import re

from telegram.constants import ChatAction


async def coroutine_wrapper(normal_function, *args, **kwargs):
	return await asyncio.to_thread(normal_function, *args, **kwargs)


async def async_func(normal_function, *args, **kwargs):
	return await coroutine_wrapper(normal_function, *args, **kwargs)


async def send_typing_action(update):
	while True:
		await update.message.reply_chat_action(action=ChatAction.TYPING)
		# 每隔4秒发送一次“正在输入...”状态
		await asyncio.sleep(4)


def escape_markdown_v2(text: str) -> str:
	"""
	Escape special characters for Telegram MarkdownV2.
	"""
	escape_chars = r'_*[]()~`>#+-=|{}.!'
	return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
