import os
from functools import lru_cache

from openai2 import Chat
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import MessageHandler, filters, ContextTypes

from utils import my_logging, validation_util

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


# 设置缓存，最多缓存100个问题的答案
@lru_cache(maxsize=100)
def get_cached_answer(question):
	return None


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
	
	# 检查缓存中是否有答案
	cached_answer = get_cached_answer(question)
	if cached_answer:
		await update.message.reply_text(cached_answer)
		return
	
	try:
		# 设置“正在输入...”状态
		await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
		
		# 异步请求答案
		answer = await chat.async_request(question)
		
		# 存入缓存
		get_cached_answer.cache_clear()
		get_cached_answer(question)
		
		await update.message.reply_text(answer)
	except Exception as e:
		logger.error(f'Error getting answer: {e}')
		await update.message.reply_text(f'Failed to get an answer from the model: \n{e}')


def handlers():
	return [
		MessageHandler(filters.TEXT & ~filters.COMMAND, answer)
	]
