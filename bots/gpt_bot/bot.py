import asyncio
import base64
import json
import os
import re
import traceback

import httpx
import openai
import telegram.helpers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.constants import ParseMode
from telegram.ext import MessageHandler, ContextTypes, CallbackContext, CommandHandler, CallbackQueryHandler, filters

from bots.gpt_bot.chat import Chat
from bots.gpt_bot.gpt_http_request import BotHttpRequest
from my_utils import my_logging, validation_util, bot_util
from my_utils.bot_util import auth

# 获取日志
logger = my_logging.get_logger('gpt_bot')

require_vars = validation_util.validate('OPENAI_API_KEY', 'OPENAI_BASE_URL')
# openai 的密钥
OPENAI_API_KEY = require_vars[0]
# 代理url
OPENAI_BASE_URL = require_vars[1]
# 默认面具
DEFAULT_MASK: str = os.getenv('DEFAULT_MASK', 'common')
# 是否启用流式传输 默认不采用
ENABLE_STREAM = int(os.getenv('ENABLE_STREAM', False))

OPENAI_COMPLETION_OPTIONS = {
	"temperature": 0.5,  # 更低的温度提高了一致性
	"top_p": 0.9,  # 采样更加多样化
	"frequency_penalty": 0.5,  # 增加惩罚以减少重复
	"presence_penalty": 0.6,  # 增加惩罚以提高新信息的引入
}

# 初始化 Chat 实例
# chat = Chat(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, max_retries=openai.DEFAULT_MAX_RETRIES,
#             timeout=openai.DEFAULT_TIMEOUT, msg_max_count=5, summary_message_threshold=500)

with open(os.path.join(os.path.dirname(__file__), 'masks.json'), encoding='utf-8') as masks_file:
	masks = json.load(masks_file)


async def start(update: Update, context: CallbackContext) -> None:
	start_message = (
		"欢迎使用！以下是您可以使用的命令列表：\n"
		"  /clear - 清除聊天\n"
		"  /masks - 切换面具\n"
		"  /model - 切换模型\n"
		"  /balance - 余额查询\n\n"
		"如需进一步帮助，请随时输入相应的命令。"
	)
	await update.message.reply_text(start_message)


def compress_question(question):
	# 去除多余的空格和换行符
	question = re.sub(r'\s+', ' ', question).strip()
	
	# 删除停用词（这里只是一个简单示例，可以根据需要扩展）
	stop_words = {'的', '是', '在', '和', '了', '有', '我', '也', '不', '就', '与', '他', '她', '它'}
	question_words = question.split()
	compressed_question = ' '.join([word for word in question_words if word not in stop_words])
	
	return compressed_question


@auth
async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if not update.message:
		return  # 无用消息
	
	is_image_generator = context.user_data.get('current_mask', masks[DEFAULT_MASK])['name'] == '图像生成助手'
	
	init_message_task = None
	if ENABLE_STREAM:
		message_text = '正在生成图片，请稍候...' if is_image_generator else '正在输入...'
		init_message_task = asyncio.create_task(
			update.message.reply_text(message_text, reply_to_message_id=update.message.message_id)
		)
	
	flag_key = None  # typing...相关 flag_key
	typing_task = None  # typing...任务
	max_length = 4096
	
	try:
		if update.message.text:
			content_task = asyncio.create_task(handle_text(update, max_length))
		elif update.message.photo:
			content_task = asyncio.create_task(handle_photo(update, context, max_length))
		elif update.message.document:
			content_task = asyncio.create_task(handle_document(update, context, max_length))
		elif update.message.audio or update.message.voice:
			content_task = asyncio.create_task(handle_audio(update, context))
		elif update.message.video:
			content_task = asyncio.create_task(handle_video(update, context))
		else:
			raise ValueError('不支持的输入类型!')
		
		curr_mask = context.user_data.get('current_mask', masks[DEFAULT_MASK])
		
		OPENAI_COMPLETION_OPTIONS.update({
			'messages': curr_mask['mask'],
			'model': context.user_data.get('current_model', curr_mask['default_model'])
		})
		
		if 'chat' not in context.user_data:
			chat_init_params = {
				"api_key": OPENAI_API_KEY,
				"base_url": OPENAI_BASE_URL,
				"max_retries": openai.DEFAULT_MAX_RETRIES,
				"timeout": openai.DEFAULT_TIMEOUT,
				"msg_max_count": 5
			}
			context.user_data['chat'] = Chat(**chat_init_params)
		
		content_result = await content_task
		
		if ENABLE_STREAM:
			await handle_stream_response(update, context, content_result, is_image_generator, init_message_task)
		else:
			flag_key = update.message.message_id
			context.user_data[flag_key] = True
			typing_task = asyncio.create_task(bot_util.send_typing_action(update, context, flag_key))
			
			await handle_response(update, context, content_result, is_image_generator, flag_key)
	except Exception as e:
		await handle_exception(update, context, e, init_message_task, flag_key)
	finally:
		if typing_task and not typing_task.done():
			typing_task.cancel()


async def handle_caption(update: Update, max_length):
	if update.message.caption:
		handled_question = compress_question(update.message.caption.strip())
		if len(handled_question) > max_length:
			raise ValueError(f'Your question is too long. Please limit it to {max_length} characters.')
		return handled_question
	return None


async def handle_photo_download(update: Update, context: CallbackContext):
	photo = update.message.photo[-2]
	photo_file = await context.bot.get_file(photo.file_id)
	async with httpx.AsyncClient() as client:
		photo_response = await client.get(photo_file.file_path)
	image_data = photo_response.content
	if image_data:
		return base64.b64encode(image_data).decode("utf-8")
	else:
		raise ValueError("Empty image data received.")


async def handle_photo(update, context, max_length):
	content = []
	current_mask = context.user_data.get('current_mask', masks[DEFAULT_MASK])
	if current_mask['name'] != '图像解析助手':
		raise ValueError(
			f'请将面具切换为"图像解析助手"!')
	
	handle_result = await asyncio.gather(handle_caption(update, max_length),
	                                     handle_photo_download(update, context))
	caption_result = handle_result[0]
	photo_download_result = handle_result[1]
	if caption_result:
		content.append({'type': 'text', 'text': caption_result})
	if photo_download_result:
		content.append({'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{photo_download_result}'}})
	return content


async def handle_document_download(update: Update, context: CallbackContext):
	document = update.message.document
	file = await context.bot.get_file(document.file_id)
	async with httpx.AsyncClient() as client:
		response = await client.get(file.file_path)
	document_text = response.text
	return f'```{document.mime_type}\n{document_text}\n```\n'


async def handle_document(update, context, max_length):
	handled_result = await asyncio.gather(handle_document_download(update, context),
	                                      handle_caption(update, max_length))
	handle_document_result = handled_result[0]
	handle_caption_result = handled_result[1]
	return handle_document_result + (handle_caption_result if handle_caption_result else '')


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


async def handle_stream_response(update, context, content, is_image_generator, init_message_task):
	prev_answer = ''
	chat: Chat = context.user_data['chat']
	init_message: Message = await init_message_task
	current_message_id = init_message.message_id
	current_message_length = 0
	MAX_MESSAGE_LENGTH = 4096  # 测试用较小的值
	message_content = ''
	
	async for status, curr_answer in chat.async_stream_request(content, chat.is_free, **OPENAI_COMPLETION_OPTIONS):
		if is_image_generator:
			async with httpx.AsyncClient() as client:
				img_response = await client.get(curr_answer)
			if img_response.content:
				await asyncio.gather(
					bot_util.edit_message(update, context, current_message_id, True, '图片生成成功! 正在发送...'),
					update.message.reply_photo(photo=img_response.content,
					                           reply_to_message_id=update.effective_message.message_id))
			continue
		if abs(len(curr_answer) - len(prev_answer)) < 100 and status != 'finished':
			continue
		new_content = curr_answer[len(prev_answer):]
		new_content_length = len(new_content)
		if current_message_length + new_content_length > MAX_MESSAGE_LENGTH:
			new_init_message = await context.bot.send_message(chat_id=update.message.chat_id, text='正在输入...')
			current_message_id = new_init_message.message_id
			current_message_length = 0
			message_content = ''
		if new_content:
			message_content += new_content
			if message_content != prev_answer:
				await bot_util.edit_message(update, context, current_message_id, status == 'finished', message_content)
				current_message_length += new_content_length
		prev_answer = curr_answer


async def handle_response(update, context, content, is_image_generator, flag_key):
	chat: Chat = context.user_data['chat']
	async for res in chat.async_request(content, **OPENAI_COMPLETION_OPTIONS):
		if res is None or len(res) == 0:
			continue
		if is_image_generator:
			async with httpx.AsyncClient() as client:
				# 将res的url下载 返回一个图片
				img_response = await client.get(res)
				context.user_data[flag_key] = False
			if img_response.content:
				await update.message.reply_photo(photo=img_response.content,
				                                 reply_to_message_id=update.effective_message.message_id)
		else:
			context.user_data[flag_key] = False
			if len(res) < 4096:
				await bot_util.send_message(update, res)
			else:
				parts = [res[i:i + 4096] for i in range(0, len(res), 4096)]
				for part in parts:
					await bot_util.send_message(update, part)


async def handle_exception(update, context, e, init_message_task, flag_key):
	logger.error(
		f"==================================================ERROR START==================================================================")
	# 记录异常信息
	logger.error(f"Exception occurred: {e}")
	traceback.print_exc()
	logger.error(
		f"==================================================ERROR END====================================================================")
	if flag_key:
		context.user_data[flag_key] = False
	error_message = str(e)
	if 'at byte offset' in error_message:
		await exception_message_handler(update, context, init_message_task, '缺少结束标记!')
	elif 'content_filter' in error_message:
		await exception_message_handler(update, context, init_message_task,
		                                "The response was filtered due to the prompt triggering Azure OpenAI's content management policy. Please modify your prompt and retry!")
	elif '504 Gateway Time-out' in error_message:
		await exception_message_handler(update, context, init_message_task, '网关超时!')
	else:
		match = re.search(r"message': '(.+?) \(request id:", error_message)
		if match:
			clean_message = match.group(1)
			text = f'Exception occurred:: \n\n{clean_message}'
		else:
			text = f'Exception occurred: \n\n{e}'
		await exception_message_handler(update, context, init_message_task, text)


async def exception_message_handler(update, context, init_message_task, text):
	if init_message_task:
		init_message = await init_message_task
		await bot_util.edit_message(update, context, init_message.message_id, True, text)
	else:
		await bot_util.send_message(update, text)


@auth
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
		if not typing_task.done():
			typing_task.cancel()


@auth
async def clear_handler(update: Update, context: CallbackContext):
	"""
	清除上下文
	Args:
		update: 更新
		context:  上下文对象
	"""
	if 'chat' not in context.user_data:
		# 初始化chat
		context.user_data['chat'] = Chat(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL,
		                                 max_retries=openai.DEFAULT_MAX_RETRIES,
		                                 timeout=openai.DEFAULT_TIMEOUT, msg_max_count=5)
	# 创建内联按钮
	keyboard = [
		[InlineKeyboardButton("恢复上下文", callback_data='restore_context')]
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	task = asyncio.create_task(update.message.reply_text('上下文已清除', reply_markup=reply_markup))
	# 清空历史消息
	context.user_data['chat'].clear_messages(context)
	await task


# 处理按钮点击事件
async def restore_context_handler(update: Update, context: CallbackContext):
	query = update.callback_query
	await query.answer()
	
	# 检查按钮的回调数据
	if query.data == 'restore_context':
		task = asyncio.create_task(query.edit_message_text(text="上下文已恢复"))
		context.user_data['chat'].recover_messages(context)
		await task


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


@auth
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
	switch_success_message_task = asyncio.create_task(query.edit_message_text(
		text=f'面具已切换至*{selected_mask["name"]}*',
		parse_mode=ParseMode.MARKDOWN_V2
	))
	if 'chat' not in context.user_data:
		chat_init_params = {
			"api_key": OPENAI_API_KEY,
			"base_url": OPENAI_BASE_URL,
			"max_retries": openai.DEFAULT_MAX_RETRIES,
			"timeout": openai.DEFAULT_TIMEOUT,
			"msg_max_count": 5
		}
		context.user_data['chat'] = Chat(**chat_init_params)
	else:
		# 切换面具后清除上下文
		context.user_data['chat'].clear_messages(context)
	await switch_success_message_task


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


@auth
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
	switch_model_task = asyncio.create_task(query.edit_message_text(
		text=f'模型已切换至*{telegram.helpers.escape_markdown(selected_model, version=2)}*',
		parse_mode=ParseMode.MARKDOWN_V2
	))
	if 'chat' not in context.user_data:
		chat_init_params = {
			"api_key": OPENAI_API_KEY,
			"base_url": OPENAI_BASE_URL,
			"max_retries": openai.DEFAULT_MAX_RETRIES,
			"timeout": openai.DEFAULT_TIMEOUT,
			"msg_max_count": 5
		}
		context.user_data['chat'] = Chat(**chat_init_params)
	else:
		# 切换模型后清除上下文
		context.user_data['chat'].clear_messages(context)
	await switch_model_task


def handlers():
	return [
		CommandHandler('start', start),
		CommandHandler('clear', clear_handler),
		CommandHandler('masks', masks_handler),
		CommandHandler('model', model_handler),
		CallbackQueryHandler(mask_selection_handler,
		                     pattern='^(common|github_copilot|image_generator|image_analyzer|travel_guide|song_recommender|movie_expert|doctor)$'),
		CallbackQueryHandler(model_selection_handler, pattern='^(gpt-|dall)'),
		CallbackQueryHandler(restore_context_handler, pattern='^(restore_context)$'),
		CommandHandler('balance', balance_handler),
		MessageHandler(
			filters.TEXT & ~filters.COMMAND | filters.ATTACHMENT, answer)
	]
