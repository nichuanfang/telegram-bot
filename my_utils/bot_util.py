import asyncio

from telegram.constants import ChatAction


async def send_typing_action(update):
	while True:
		await update.message.reply_chat_action(action=ChatAction.TYPING)
		# 每隔4秒发送一次“正在输入...”状态
		await asyncio.sleep(4)