import asyncio
import json
import os
import re

import telegram
from openai2 import Chat
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes, CallbackContext, CommandHandler

from bots.gpt_bot.gpt_http_request import BotHttpRequest
from my_utils import my_logging, validation_util, bot_util

# 获取日志
logger = my_logging.get_logger('tmdb_bot')

require_vars = validation_util.validate('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'ALLOWED_TELEGRAM_USER_IDS')
# openai 的密钥
OPENAI_API_KEY = require_vars[0]
# 代理url
OPENAI_BASE_URL = require_vars[1]
# 允许访问的用户列表 逗号分割并去除空格
ALLOWED_TELEGRAM_USER_IDS = [user_id.strip() for user_id in require_vars[2].split(',')]
# 模型
OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')

# 初始化 Chat 实例
chat = Chat(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, model=OPENAI_MODEL, msg_max_count=2)

# 授权
def auth(user_id: str) -> bool:
	return str(user_id) in ALLOWED_TELEGRAM_USER_IDS


def compress_question(question):
	# 去除多余的空格和换行符
	question = re.sub(r'\s+', ' ', question).strip()
	
	# 删除停用词（这里只是一个简单示例，可以根据需要扩展）
	stop_words = {'的', '是', '在', '和', '了', '有', '我', '也', '不', '就', '与', '他', '她', '它'}
	question_words = question.split()
	compressed_question = ' '.join([word for word in question_words if word not in stop_words])
	
	return compressed_question


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	user_id = update.effective_user.id
	if not auth(user_id):
		await update.message.reply_text('You are not authorized to use this bot.')
		return
	
	question = update.effective_message.text.strip()
	
	# 限制问题的长度，避免过长的问题
	max_length = 400
	if len(question) > max_length:
		await update.message.reply_text(f'Your question is too long. Please limit it to {max_length} characters.')
		return
	
	# 压缩问题内容
	compressed_question = compress_question(question)
	
	try:
		# 开始发送“正在输入...”状态
		typing_task = asyncio.create_task(bot_util.send_typing_action(update))
		
		request_options = {
			"temperature": 0.5,
			"presence_penalty": 0,
			"frequency_penalty": 0,
			"top_p": 1
		}
		# chat.add_dialogs({"role": "system", "content": '你是一个全能的回复专家.能自动判断用户提问涉及的领域,在保证回答质量的情况下精简回复的内容'})
		# 异步请求答案
		answer = await chat.async_request(compressed_question, **request_options)
		
		# 停止发送“正在输入...”状态
		typing_task.cancel()
		
		await update.message.reply_text(telegram.helpers.escape_markdown(answer, version=2), parse_mode='MarkdownV2')
	except Exception as e:
		logger.error(f'Error getting answer: {e}')
		await update.message.reply_text(f'Failed to get an answer from the model: \n{e}')


async def balance_handler(update: Update, context: CallbackContext):
	typing_task = asyncio.create_task(bot_util.send_typing_action(update))
	request = BotHttpRequest()
	try:
		responses = await asyncio.gather(request.get_subscription(), request.get_usage())
		subscription = responses[0]
		usage = responses[1]
		total = json.loads(subscription.text)['soft_limit_usd']
		used = json.loads(usage.text)['total_usage'] / 100
		typing_task.cancel()
		await update.message.reply_text(f'已使用 ${round(used, 2)} , 订阅总额 ${round(total, 2)}')
	except Exception as e:
		await update.message.reply_text(f'获取余额失败: {e}')


def handlers():
	return [
		CommandHandler('balance', balance_handler),
		MessageHandler(filters.TEXT & ~filters.COMMAND, answer),
	]
