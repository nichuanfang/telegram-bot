import asyncio
import json
import os
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import MessageHandler, filters, ContextTypes, CallbackContext, CommandHandler, CallbackQueryHandler

from bots.gpt_bot.chat import Chat
from bots.gpt_bot.gpt_http_request import BotHttpRequest
from my_utils import my_logging, validation_util, bot_util

# 获取日志
logger = my_logging.get_logger('gpt_bot')

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
chat = Chat(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, model=OPENAI_MODEL, msg_max_count=10)

masks = {
	'common': {
		'name': '通用助手',
		'mask': [{"role": "system",
		          "content": '你是一个全能的问题回复专家,你能以最精简的方式提供最优的内容质量'}]
	},
	'github_copilot': {
		'name': '代码助手',
		'mask': [{"role": "system",
		          "content": '你是软件开发专家,你可以为我解答任何关于功能设计,bug修复,代码优化等软件开发方面的问题'}]
	},
	'travel_guide': {
		'name': '旅游助手',
		'mask': [{"role": "system",
		          "content": '你是高级聊天机器人旅游指南。您的主要目标是为用户提供有关其旅行目的地的有用信息和建议，包括景点、住宿、交通和当地习俗'}]
	},
	'movie_expert': {
		'name': '电影专家',
		'mask': [{"role": "system",
		          "content": '作为高级聊天机器人电影专家助理，您的主要目标是尽您所能为用户提供帮助。您可以回答有关电影、演员、导演等的问题。您可以根据用户的喜好向他们推荐电影。您可以与用户讨论电影，并提供有关电影的有用信息。为了有效地帮助用户，在回复中保持详细和彻底是很重要的。使用示例和证据来支持您的观点并证明您的建议或解决方案的合理性。请记住始终优先考虑用户的需求和满意度。您的最终目标是为用户提供有用且愉快的体验'}]
	},
	'doctor': {
		'name': '医生',
		'mask': [{"role": "system",
		          "content": '我想让你扮演一名人工智能辅助医生.我将为您提供患者的详细信息,您的任务是使用最新的人工智能工具,例如医学成像软件和其他机器学习程序,以诊断最可能导致其症状的原因.您还应该将体检、实验室测试等传统方法纳入您的评估过程,以确保准确性'}]
	}
}


async def start(update: Update, context: CallbackContext) -> None:
	start_message = (
		"欢迎使用！以下是您可以使用的命令列表：\n"
		"  /clear - 清除聊天\n"
		"  /masks - 切换面具\n"
		"  /balance - 余额查询\n\n"
		"如需进一步帮助，请随时输入相应的命令。"
	)
	await update.message.reply_text(start_message)


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
	max_length = 1000
	if len(question) > max_length:
		await update.message.reply_text(f'Your question is too long. Please limit it to {max_length} characters.')
		return
	
	# 压缩问题内容
	compressed_question = compress_question(question)
	
	# 开始发送“正在输入...”状态
	typing_task = asyncio.create_task(bot_util.send_typing_action(update))
	curr_mask = context.user_data.get('current_mask', masks['common'])
	request_options = {
		'messages': curr_mask['mask'],
		"temperature": 0.5,
		"presence_penalty": 0,
		"frequency_penalty": 0,
		"top_p": 1
	}
	
	buffer = ''
	buffer_limit = 50  # 可以根据需要调整
	
	try:
		# 发送初始消息
		sent_message = await update.message.reply_text('Loading...')
		message_id = sent_message.message_id
		total_answer = ''
		
		async for answer in chat.async_stream_request(compressed_question, **request_options):
			buffer += answer.replace('**', '')
			if len(buffer) >= buffer_limit:
				total_answer += buffer
				# 修改消息
				await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message_id,
				                                    text=total_answer)
				buffer = ''
		
		# 发送剩余的字符
		if buffer:
			total_answer += buffer
			await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message_id,
			                                    text=total_answer)
	
	except Exception as e:
		logger.error(f'Error getting answer: {e}')
		await update.message.reply_text(f'Failed to get an answer from the model: \n{e}')
	finally:
		# 停止发送“正在输入...”状态
		typing_task.cancel()


async def balance_handler(update: Update, context: CallbackContext):
	typing_task = asyncio.create_task(bot_util.send_typing_action(update))
	request = BotHttpRequest()
	try:
		responses = await asyncio.gather(request.get_subscription(), request.get_usage())
		subscription = responses[0]
		usage = responses[1]
		total = json.loads(subscription.text)['soft_limit_usd']
		used = json.loads(usage.text)['total_usage'] / 100
		await update.message.reply_text(f'已使用 ${round(used, 2)} , 订阅总额 ${round(total, 2)}')
		typing_task.cancel()
	except Exception as e:
		await update.message.reply_text(f'获取余额失败: {e}')
		typing_task.cancel()


async def clear_handler(update: Update, context: CallbackContext):
	"""
	清除上下文
	Args:
		update: 更新
		context:  上下文对象
	"""
	# 清空历史消息
	chat.clear_messages()
	await update.message.reply_text('上下文已清除')


async def masks_handler(update: Update, context: CallbackContext):
	"""
	切换面具处理器
	Args:
		update:  更新对象
		context:  上下文对象
	"""
	# 创建内联键盘按钮
	keyboard = [
		[InlineKeyboardButton(masks[key]['name'], callback_data=key) for key in masks]
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	
	await update.message.reply_text(
		'请选择一个面具:',
		reply_markup=reply_markup
	)


async def mask_selection_handler(update: Update, context: CallbackContext):
	"""
	处理面具选择
	Args:
		update:  更新对象
		context:  上下文对象
	"""
	query = update.callback_query
	await query.answer()
	
	# 获取用户选择的面具
	selected_mask_key = query.data
	selected_mask = masks[selected_mask_key]
	
	# 根据选择的面具进行相应的处理
	await query.edit_message_text(
		text=f'面具已切换至*{selected_mask["name"]}*',
		parse_mode=ParseMode.HTML
	)
	
	# 切换面具后清除上下文
	chat.clear_messages()
	
	# 应用选择的面具
	context.user_data['current_mask'] = selected_mask['mask']


def handlers():
	return [
		CommandHandler('start', start),
		CommandHandler('clear', clear_handler),
		CommandHandler('masks', masks_handler),
		CallbackQueryHandler(mask_selection_handler),
		CommandHandler('balance', balance_handler),
		MessageHandler(filters.TEXT & ~filters.COMMAND, answer),
	]
