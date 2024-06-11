import asyncio
import base64
import json
import os
import re

import requests
import telegram.helpers
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
OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo-0125')
# 可用的模型列表
MODELS = ['gpt-3.5-turbo-0125', 'gpt-4o-2024-05-13']
# 是否启用流式传输 默认不采用
ENABLE_STREAM = int(os.getenv('ENABLE_STREAM', False))
# 初始化 Chat 实例
chat = Chat(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, msg_max_count=10)

OPENAI_COMPLETION_OPTIONS = {
	"temperature": 0.5,  # 更低的温度提高了一致性
	"max_tokens": 4000,  # 根据需求调整token长度
	"top_p": 0.9,  # 采样更加多样化
	"frequency_penalty": 0.5,  # 增加惩罚以减少重复
	"presence_penalty": 0.6,  # 增加惩罚以提高新信息的引入,
	"model": OPENAI_MODEL
}

masks = {
	'common': {
		'name': '通用助手',
		'mask': [{"role": "system", "content": '你是一个全能的问题回复专家，你能以最精简的方式提供最优的内容质量。'}]
	},
	'github_copilot': {
		'name': '代码助手',
		'mask': [{"role": "system",
		          "content": '你是软件开发专家，你可以为我解答任何关于功能设计、bug修复、代码优化等软件开发方面的问题。'}]
	},
	'travel_guide': {
		'name': '旅游助手',
		'mask': [{"role": "system",
		          "content": '你是高级聊天机器人旅游指南。你的主要目标是为用户提供有关其旅行目的地的有用信息和建议，包括景点、住宿、交通和当地习俗。'}]
	},
	'song_recommender': {
		'name': '歌曲推荐人',
		'mask': [{"role": "system",
		          "content": '我想让你担任歌曲推荐人。我将为你提供一首歌曲，你将创建一个包含 10 首与给定歌曲相似的歌曲的播放列表。你将为播放列表提供播放列表名称和描述。不要选择同名或同名歌手的歌曲。不要写任何解释或其他文字，只需回复播放列表名称、描述和歌曲。'}]
	},
	'movie_expert': {
		'name': '电影专家',
		'mask': [{"role": "system",
		          "content": '作为高级聊天机器人电影专家助理，你的主要目标是尽你所能为用户提供帮助。你可以回答有关电影、演员、导演等的问题。你可以根据用户的喜好向他们推荐电影。你可以与用户讨论电影，并提供有关电影的有用信息。为了有效地帮助用户，在回复中保持详细和彻底是很重要的。使用示例和证据来支持你的观点并证明你的建议或解决方案的合理性。请记住始终优先考虑用户的需求和满意度。你的最终目标是为用户提供有用且愉快的体验。'}]
	},
	'doctor': {
		'name': '医生',
		'mask': [{"role": "system",
		          "content": '我想让你扮演一名人工智能辅助医生。我将为你提供患者的详细信息，你的任务是使用最新的人工智能工具，例如医学成像软件和其他机器学习程序，以诊断最可能导致其症状的原因。你还应该将体检、实验室测试等传统方法纳入你的评估过程，以确保准确性。'}]
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
	# 开始发送“正在输入...”状态
	typing_task = asyncio.create_task(bot_util.send_typing_action(update))
	context.user_data['typing_task'] = typing_task
	# 限制问题的长度，避免过长的问题
	max_length = 6000
	# 检查是否有图片
	if update.message.photo:
		current_model = OPENAI_COMPLETION_OPTIONS['model']
		if current_model.lower().startswith('gpt-3.5'):
			try:
				await update.message.reply_text(f'当前模型: {current_model}不支持图片识别,请切换模型!')
				return
			finally:
				typing_task.cancel()
				context.user_data['typing_task'] = None
		content = []
		if update.message.caption:
			handled_question = compress_question(update.message.caption.strip())
			if len(handled_question) > max_length:
				try:
					await update.message.reply_text(
						f'Your question is too long. Please limit it to {max_length} characters.')
					return
				finally:
					typing_task.cancel()
					context.user_data['typing_task'] = None
			content.append({
				'type': 'text',
				'text': handled_question
			})
		try:
			photo = update.message.photo[-2]
			photo_file = await context.bot.get_file(photo.file_id)
			response = requests.get(photo_file.file_path)
			image_data = response.content
			if image_data:  # Check if image data is not empty
				encoded_image = base64.b64encode(image_data).decode("utf-8")
				content.append({
					'type': 'image_url',
					'image_url': {
						'url': f'data:image/jpeg;base64,{encoded_image}'
					}
				})
			else:
				raise ValueError("Empty image data received.")
		except Exception as e:
			try:
				await update.message.reply_text(f'图片识别失败!: {e}')
				return
			finally:
				typing_task.cancel()
				context.user_data['typing_task'] = None
	else:
		content = update.effective_message.text.strip()
		# 压缩问题内容
		content = compress_question(content)
		if len(content) > max_length:
			try:
				await update.message.reply_text(
					f'Your question is too long. Please limit it to {max_length} characters.')
				return
			finally:
				typing_task.cancel()
				context.user_data['typing_task'] = None
	
	curr_mask = context.user_data.get('current_mask', masks['common'])
	OPENAI_COMPLETION_OPTIONS['messages'] = curr_mask['mask']
	try:
		if ENABLE_STREAM:
			buffer = ''
			buffer_limit = 100
			# 发送初始消息
			sent_message = await update.message.reply_text('Loading...', reply_to_message_id=update.message.message_id)
			message_id = sent_message.message_id
			total_answer = ''
			
			async for res in chat.async_stream_request(content, **OPENAI_COMPLETION_OPTIONS):
				buffer += res
				if len(buffer) >= buffer_limit:
					total_answer += buffer
					# 修改消息
					await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message_id,
					                                    text=bot_util.escape_markdown_v2(total_answer),
					                                    parse_mode=ParseMode.MARKDOWN_V2)
					buffer = ''
			# 发送剩余的字符
			if buffer:
				total_answer += buffer
				await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message_id,
				                                    text=bot_util.escape_markdown_v2(total_answer),
				                                    parse_mode=ParseMode.MARKDOWN_V2)
		else:
			res = await chat.async_request(content, **OPENAI_COMPLETION_OPTIONS)
			await update.message.reply_text(bot_util.escape_markdown_v2(res)[:4096],
			                                reply_to_message_id=update.message.message_id,
			                                parse_mode=ParseMode.MARKDOWN_V2)
	except Exception as e:
		await update.message.reply_text(f'Failed to get an answer from the model: \n{e}')
		chat.drop_last_message()
	finally:
		# 停止发送“正在输入...”状态
		typing_task.cancel()
		context.user_data['typing_task'] = None


async def balance_handler(update: Update, context: CallbackContext):
	typing_task = asyncio.create_task(bot_util.send_typing_action(update))
	context.user_data['typing_task'] = typing_task
	request = BotHttpRequest()
	try:
		responses = await asyncio.gather(request.get_subscription(), request.get_usage())
		subscription = responses[0]
		usage = responses[1]
		total = json.loads(subscription.text)['soft_limit_usd']
		used = json.loads(usage.text)['total_usage'] / 100
		await update.message.reply_text(f'已使用 ${round(used, 2)} , 订阅总额 ${round(total, 2)}',
		                                reply_to_message_id=update.message.message_id)
	
	except Exception as e:
		await update.message.reply_text(f'获取余额失败: {e}')
	finally:
		typing_task.cancel()
		context.user_data['typing_task'] = None


async def clear_handler(update: Update, context: CallbackContext):
	"""
	清除上下文
	Args:
		update: 更新
		context:  上下文对象
	"""
	# 清空历史消息
	chat.clear_messages()
	typing_task = context.user_data['typing_task']
	if typing_task:
		typing_task.cancel()
		context.user_data['typing_task'] = None
	await update.message.reply_text('上下文已清除')


def generate_mask_keyboard(masks, current_mask_key):
	keyboard = []
	row = []
	for i, (key, mask) in enumerate(masks.items()):
		# 如果是当前选择的面具，添加标记
		name = mask["name"]
		if key == current_mask_key:
			name = "* " + name
		row.append(InlineKeyboardButton(name, callback_data=key))
		if (i + 1) % 3 == 0:
			keyboard.append(row)
			row = []
	if row:
		keyboard.append(row)
	return InlineKeyboardMarkup(keyboard)


async def masks_handler(update: Update, context: CallbackContext):
	"""
	切换面具处理器
	Args:
		update:  更新对象
		context:  上下文对象
	"""
	# 获取当前选择的面具
	current_mask = context.user_data.get('current_mask', masks['common'])
	current_mask_key = next(key for key, value in masks.items() if value == current_mask)
	# 生成内联键盘
	keyboard = generate_mask_keyboard(masks, current_mask_key)
	
	await update.message.reply_text(
		'请选择一个面具:',
		reply_markup=keyboard
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
		parse_mode=ParseMode.MARKDOWN_V2
	)
	# 清除未结束的typing任务
	typing_task = context.user_data['typing_task']
	if typing_task:
		typing_task.cancel()
		context.user_data['typing_task'] = None
	# 切换面具后清除上下文
	chat.clear_messages()
	
	# 应用选择的面具
	context.user_data['current_mask'] = selected_mask


# 生成模型选择键盘
def generate_model_keyboard(models, current_model):
	keyboard = []
	row = []
	for i, model in enumerate(models):
		# 如果是当前选择的模型，添加标记
		name = model
		if model == current_model:
			name = "* " + name
		row.append(InlineKeyboardButton(name, callback_data=model))
		if (i + 1) % 2 == 0:
			keyboard.append(row)
			row = []
	if row:
		keyboard.append(row)
	return InlineKeyboardMarkup(keyboard)


async def model_handler(update: Update, context: CallbackContext):
	"""
	切换模型处理器
	Args:
		update:  更新对象
		context:  上下文对象
	"""
	# 获取当前选择的模型
	current_model = OPENAI_COMPLETION_OPTIONS['model']
	# 生成内联键盘
	keyboard = generate_model_keyboard(MODELS, current_model)
	
	await update.message.reply_text(
		'请选择一个模型:',
		reply_markup=keyboard
	)


async def model_selection_handler(update: Update, context: CallbackContext):
	"""
	处理模型选择
	Args:
		update:  更新对象
		context:  上下文对象
	"""
	query = update.callback_query
	await query.answer()
	
	# 获取用户选择的模型
	selected_model = query.data
	
	# 根据选择的模型进行相应的处理
	await query.edit_message_text(
		text=f'模型已切换至*{telegram.helpers.escape_markdown(selected_model, version=2)}*',
		parse_mode=ParseMode.MARKDOWN_V2
	)
	# 清除未结束的typing任务
	typing_task = context.user_data['typing_task']
	if typing_task:
		typing_task.cancel()
		context.user_data['typing_task'] = None
	# 切换模型后清除上下文
	chat.clear_messages()
	
	# 应用选择的模型
	OPENAI_COMPLETION_OPTIONS['model'] = selected_model


def handlers():
	return [
		CommandHandler('start', start),
		CommandHandler('clear', clear_handler),
		CommandHandler('masks', masks_handler),
		CommandHandler('model', model_handler),
		CallbackQueryHandler(mask_selection_handler,
		                     pattern='^(common|github_copilot|travel_guide|song_recommender|movie_expert|doctor)$'),
		CallbackQueryHandler(model_selection_handler, pattern='^(gpt-|dall)'),
		CommandHandler('balance', balance_handler),
		MessageHandler(filters.ALL & ~filters.COMMAND, answer)
	]
