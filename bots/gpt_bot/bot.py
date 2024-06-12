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
# 默认面具
DEFAULT_MASK: str = os.getenv('DEFAULT_MASK', 'common')
# 是否启用流式传输 默认不采用
ENABLE_STREAM = int(os.getenv('ENABLE_STREAM', False))
# 初始化 Chat 实例
chat = Chat(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, msg_max_count=10)

OPENAI_COMPLETION_OPTIONS = {
	"temperature": 0.5,  # 更低的温度提高了一致性
	"top_p": 0.9,  # 采样更加多样化
	"frequency_penalty": 0.5,  # 增加惩罚以减少重复
	"presence_penalty": 0.6,  # 增加惩罚以提高新信息的引入
}

with open(os.path.join(os.path.dirname(__file__), 'masks.json'), encoding='utf-8') as masks_file:
	masks = json.load(masks_file)


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
	
	flag_key = update.message.message_id
	context.user_data[flag_key] = True
	typing_task = asyncio.create_task(bot_util.send_typing_action(update, context, flag_key))
	
	max_length = 4096
	try:
		if update.message.photo:
			content = await handle_photo(update, context, max_length)
		elif update.message.document:
			content = await handle_document(update, context, max_length)
		elif update.message.audio or update.message.voice:
			content = await handle_audio(update, context)
		elif update.message.video:
			content = await handle_video(update, context)
		else:
			content = await handle_text(update, max_length)
		
		# 获取面具
		curr_mask = context.user_data.get('current_mask', masks[DEFAULT_MASK])
		# 设置面具内容
		OPENAI_COMPLETION_OPTIONS['messages'] = curr_mask['mask']
		# 选择模型
		current_model = context.user_data.get('current_model', curr_mask['default_model'])
		# 设置模型
		OPENAI_COMPLETION_OPTIONS['model'] = current_model
		
		if ENABLE_STREAM:
			await handle_stream_response(update, context, content)
		else:
			await handle_response(update, context, content, flag_key)
	
	except Exception as e:
		await handle_exception(update, context, e, flag_key)
	finally:
		await typing_task


async def handle_photo(update, context, max_length):
	content = []
	current_mask = context.user_data.get('current_mask', masks[DEFAULT_MASK])
	if current_mask['name'] != '图像解析助手':
		raise ValueError(
			f'请将面具切换为"图像解析助手"!')
	
	if update.message.caption:
		handled_question = compress_question(update.message.caption.strip())
		if len(handled_question) > max_length:
			raise ValueError(f'Your question is too long. Please limit it to {max_length} characters.')
		content.append({'type': 'text', 'text': handled_question})
	
	photo = update.message.photo[-2]
	photo_file = await context.bot.get_file(photo.file_id)
	response = requests.get(photo_file.file_path)
	image_data = response.content
	if image_data:
		encoded_image = base64.b64encode(image_data).decode("utf-8")
		content.append({'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{encoded_image}'}})
	else:
		raise ValueError("Empty image data received.")
	return content


async def handle_document(update, context, max_length):
	document = update.message.document
	file = await context.bot.get_file(document.file_id)
	response = requests.get(file.file_path)
	document_text = response.text
	content = f'```{document.mime_type}\n{document_text}\n```\n'
	
	if update.message.caption:
		handled_question = compress_question(update.message.caption.strip())
		if len(handled_question) > max_length:
			raise ValueError(f'Your question is too long. Please limit it to {max_length} characters.')
		content = content + handled_question
	return content


async def handle_audio(update, context):
	audio_file = update.message.audio or update.message.voice
	if audio_file:
		file_id = audio_file.file_id
		new_file = await context.bot.get_file(file_id)
		file_path = os.path.join(f"{file_id}.ogg")
		await new_file.download_to_drive(file_path)
		try:
			return {
				'type': 'audio',
				'audio_path': file_path
			}
		except Exception as e:
			raise ValueError(e)


async def handle_video(update, context):
	return "Video processing is not implemented yet."


async def handle_text(update, max_length):
	content_text = update.effective_message.text.strip()
	content_text = compress_question(content_text)
	if len(content_text) > max_length:
		raise ValueError(f'Your question is too long. Please limit it to {max_length} characters.')
	return content_text


async def handle_stream_response(update, context, content):
	buffer = ''
	buffer_limit = 100
	sent_message = await update.message.reply_text('Loading...', reply_to_message_id=update.message.message_id)
	message_id = sent_message.message_id
	total_answer = ''
	async for res in chat.async_stream_request(content, **OPENAI_COMPLETION_OPTIONS):
		buffer += res
		if len(buffer) >= buffer_limit:
			total_answer += buffer
			await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message_id,
			                                    text=bot_util.escape_markdown_v2(total_answer),
			                                    parse_mode=ParseMode.MARKDOWN_V2)
			buffer = ''
	if buffer:
		total_answer += buffer
		await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message_id,
		                                    text=bot_util.escape_markdown_v2(total_answer),
		                                    parse_mode=ParseMode.MARKDOWN_V2)


async def handle_response(update, context, content, flag_key):
	res = await chat.async_request(content, **OPENAI_COMPLETION_OPTIONS)
	context.user_data[flag_key] = False
	if context.user_data.get('current_mask', masks[DEFAULT_MASK])['name'] == '图像生成助手':
		# 将res的url下载 返回一个图片
		img_response = requests.get(res['url'])
		if img_response.content:
			await update.message.reply_photo(photo=img_response.content, caption=res['caption'],reply_to_message_id=update.effective_message.message_id)
	else:
		if len(res) < 4096:
			await update.message.reply_text(bot_util.escape_markdown_v2(res),
			                                reply_to_message_id=update.message.message_id,
			                                parse_mode=ParseMode.MARKDOWN_V2)
		else:
			parts = [res[i:i + 4096] for i in range(0, len(res), 4096)]
			for part in parts:
				await update.message.reply_text(bot_util.escape_markdown_v2(part),
				                                reply_to_message_id=update.message.message_id,
				                                parse_mode=ParseMode.MARKDOWN_V2)


async def handle_exception(update, context, e, flag_key):
	context.user_data[flag_key] = False
	if 'at byte offset' in str(e):
		await update.message.reply_text('缺少结束标记! 请使用文本文件解析!',
		                                reply_to_message_id=update.message.message_id)
		chat.clear_messages()
	elif '504 Gateway Time-out' in str(e):
		await update.message.reply_text('网关超时!请减小文本或文件大小再进行尝试!')
		chat.clear_messages()
	else:
		match = re.search(r"message': '(.+?) \(request id:", str(e))
		if match:
			clean_message = match.group(1)
			await update.message.reply_text(f'Failed to get an answer from the model: \n\n{clean_message}',
			                                reply_to_message_id=update.message.message_id)
		else:
			await update.message.reply_text(f'Failed to get an answer from the model: \n\n{e}',
			                                reply_to_message_id=update.message.message_id)


async def balance_handler(update: Update, context: CallbackContext):
	flag_key = update.message.message_id
	# 启动一个异步任务来发送 typing 状态
	context.user_data[flag_key] = True
	typing_task = asyncio.create_task(bot_util.send_typing_action(update, context, flag_key))
	
	request = BotHttpRequest()
	try:
		responses = await asyncio.gather(request.get_subscription(), request.get_usage())
		subscription = responses[0]
		usage = responses[1]
		total = json.loads(subscription.text)['soft_limit_usd']
		used = json.loads(usage.text)['total_usage'] / 100
		context.user_data[flag_key] = False
		await update.message.reply_text(f'已使用 ${round(used, 2)} , 订阅总额 ${round(total, 2)}',
		                                reply_to_message_id=update.message.message_id)
	
	except Exception as e:
		context.user_data[flag_key] = False
		await update.message.reply_text(f'获取余额失败: {e}')
	finally:
		await typing_task


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


def generate_mask_keyboard(masks, current_mask_key):
	keyboard = []
	row = []
	for i, (key, mask) in enumerate(masks.items()):
		# 如果是当前选择的面具，添加标记
		name = mask["name"]
		if key == current_mask_key:
			name = "* " + name
		row.append(InlineKeyboardButton(name, callback_data=key))
		if (i + 1) % 2 == 0:
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
	current_mask = context.user_data.get('current_mask', masks[DEFAULT_MASK])
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
	# 应用选择的面具
	context.user_data['current_mask'] = selected_mask
	current_model = context.user_data.get('current_model')
	# 获取当前模型  如果当前模型兼容选择的面具 则无需切换模型; 如果不兼容 则需切换到该面具的默认模型
	if current_model:
		if current_model not in selected_mask['supported_models']:
			context.user_data['current_model'] = selected_mask['default_model']
	else:
		context.user_data['current_model'] = selected_mask['default_model']
	
	# 根据选择的面具进行相应的处理
	await query.edit_message_text(
		text=f'面具已切换至*{selected_mask["name"]}*',
		parse_mode=ParseMode.MARKDOWN_V2
	)
	# 切换面具后清除上下文
	chat.clear_messages()


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
	# 获取当前的面具
	current_mask = context.user_data.get('current_mask', masks['common'])
	# 获取当前选择的模型
	current_model = context.user_data.get('current_model', current_mask['default_model'])
	# 生成内联键盘
	keyboard = generate_model_keyboard(current_mask['supported_models'], current_model)
	
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
	# 应用选择的面具
	context.user_data['current_model'] = selected_model
	# 根据选择的模型进行相应的处理
	await query.edit_message_text(
		text=f'模型已切换至*{telegram.helpers.escape_markdown(selected_model, version=2)}*',
		parse_mode=ParseMode.MARKDOWN_V2
	)
	# 切换模型后清除上下文
	chat.clear_messages()


def handlers():
	return [
		CommandHandler('start', start),
		CommandHandler('clear', clear_handler),
		CommandHandler('masks', masks_handler),
		CommandHandler('model', model_handler),
		CallbackQueryHandler(mask_selection_handler,
		                     pattern='^(common|github_copilot|image_generator|image_analyzer|travel_guide|song_recommender|movie_expert|doctor)$'),
		CallbackQueryHandler(model_selection_handler, pattern='^(gpt-|dall)'),
		CommandHandler('balance', balance_handler),
		MessageHandler(filters.ALL & ~filters.COMMAND, answer)
	]
