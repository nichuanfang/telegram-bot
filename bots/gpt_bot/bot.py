import os
import re

from openai2 import Chat
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import MessageHandler, filters, ContextTypes

from my_utils import my_logging, validation_util

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
chat = Chat(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, model=OPENAI_MODEL)


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
		# 设置“正在输入...”状态
		await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
		
		# 异步请求答案
		answer = await chat.async_request(compressed_question)
		
		await update.message.reply_text(answer)
	except Exception as e:
		logger.error(f'Error getting answer: {e}')
		await update.message.reply_text(f'Failed to get an answer from the model: \n{e}')


def handlers():
	return [
		MessageHandler(filters.TEXT & ~filters.COMMAND, answer)
	]
