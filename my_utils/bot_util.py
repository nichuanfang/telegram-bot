import asyncio
import functools
import importlib
import json
import os
import re
import uuid

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from my_utils.my_logging import get_logger
from my_utils.validation_util import validate

logger = get_logger('bot_util')

values = validate('ALLOWED_TELEGRAM_USER_IDS')
# 允许访问的用户列表 逗号分割并去除空格
ALLOWED_TELEGRAM_USER_IDS = [user_id.strip() for user_id in values[0].split(',')]
# 默认平台
DEFAULT_PLATFORM: str = os.getenv('DEFAULT_PLATFORM', 'free_1')
# 模型注册表
PLATFORMS_REGISTRY = {}
# 最大历史消息数
MSG_MAX_COUNT = 5


def load_platforms():
	platforms_path = os.path.abspath(os.path.join('bots', 'gpt_bot', 'config', 'platforms.json'))
	if os.path.exists(platforms_path):
		with open(platforms_path, encoding='utf-8') as platforms_file:
			return json.load(platforms_file)
	else:
		raise RuntimeError('platforms.json不存在,无法加载平台数据!')


def register_platform():
	platforms_path = os.path.abspath(os.path.join('bots', 'gpt_bot', 'platforms'))
	for file in os.listdir(platforms_path):
		if not file.endswith('.py'):
			continue
		name = file.split(".")[0]
		platform_module = importlib.import_module(f'bots.gpt_bot.platforms.{name}')
		for attr_name in dir(platform_module):
			attr = getattr(platform_module, attr_name)
			if isinstance(attr, type) and getattr(attr, '_is_gpt_platform', False):
				platform_name = attr._platform_name()
				PLATFORMS_REGISTRY[platform_name] = attr


# 加载平台元数据
platforms = load_platforms()

# 注册平台
register_platform()


def instantiate_platform(platform_name: str = DEFAULT_PLATFORM):
	"""
	初始化平台
	@param platform_name: 平台名称(英文)  
	@return:  平台对象
	"""
	# 默认平台
	platform = platforms[platform_name]
	# 平台初始化参数
	platform_init_params = {
		'name': platform_name,
		'name_zh': platform['name'],
		'domestic_openai_base_url': platform['domestic_openai_base_url'],
		'foreign_openai_base_url': platform['foreign_openai_base_url'],
		'openai_api_key': platform['openai_api_key'],
		'index_url': platform['index_url'],
		'payment_url': platform['payment_url'],
		'msg_max_count': 2 if platform_name.startswith('free') else MSG_MAX_COUNT
	}
	logger.info(f'当前使用的openai代理平台为{platform_name}.')
	return PLATFORMS_REGISTRY[platform_name](**platform_init_params)


def auth(func):
	"""
	自定义授权装饰器
	Args:
		func: 需要授权的方法

	Returns:

	"""
	
	@functools.wraps(func)
	async def wrapper(*args, **kwargs):
		# 获取update和context
		update: Update = args[0]
		context: CallbackContext = args[1]
		user_id = update.effective_user.id
		if str(user_id) not in ALLOWED_TELEGRAM_USER_IDS:
			# 只针对GBTBot开放访问 其他机器人正常拦截
			if context.bot.first_name == 'GPTBot':
				logger.info(f'=================user {user_id} access the GPTbot for free===================')
				if 'platform' not in context.user_data:
					context.user_data['platform'] = instantiate_platform('free_1')
			else:
				logger.warn(f"======================user {user_id}'s  access has been filtered====================")
				await update.message.reply_text('You are not authorized to use this bot.')
				return
		await func(*args, **kwargs)
	
	return wrapper


async def uuid_generator():
	while True:
		yield uuid.uuid4().__str__()


async def coroutine_wrapper(normal_function, *args, **kwargs):
	return await asyncio.to_thread(normal_function, *args, **kwargs)


async def async_func(normal_function, *args, **kwargs):
	return await coroutine_wrapper(normal_function, *args, **kwargs)


async def send_typing(update: Update):
	await update.message.reply_chat_action(action='typing')


async def send_typing_action(update: Update, context: CallbackContext, flag_key):
	while context.user_data.get(flag_key, False):
		await update.message.reply_chat_action(action='typing')
		await asyncio.sleep(3)  # 每3秒发送一次 typing 状态


async def send_message(update: Update, text):
	try:
		escaped_text = escape_markdown_v2(text)  # 转义特殊字符
		return await update.message.reply_text(escaped_text,
		                                       reply_to_message_id=update.message.message_id,
		                                       disable_web_page_preview=True,
		                                       parse_mode=ParseMode.MARKDOWN_V2)
	except:
		return await update.message.reply_text(text, reply_to_message_id=update.message.message_id,
		                                       disable_web_page_preview=True)


async def edit_message(update: Update, context: CallbackContext, message_id, stream_ended, text):
	try:
		# 等流式响应完全结束再尝试markdown格式 加快速度
		if stream_ended:
			escaped_text = escape_markdown_v2(text)
			await context.bot.edit_message_text(
				text=escaped_text,
				chat_id=update.message.chat_id,
				message_id=message_id,
				disable_web_page_preview=True,
				parse_mode=ParseMode.MARKDOWN_V2
			)
		else:
			await context.bot.edit_message_text(
				text=text,
				chat_id=update.message.chat_id,
				message_id=message_id,
				disable_web_page_preview=True
			)
	except Exception:
		try:
			await context.bot.edit_message_text(
				text=text,
				chat_id=update.message.chat_id,
				message_id=message_id, disable_web_page_preview=True)
		except Exception:
			pass


def escape_markdown_v2(text: str) -> str:
	"""
	Escape special characters for Telegram MarkdownV2 and replace every pair of consecutive asterisks (**) with a single asterisk (*).
	"""
	try:
		escape_chars = r"\_[]()#~>+-=|{}.!"
		escaped_text = re.sub(f"([{re.escape(escape_chars)}])", r'\\\1', text)
		escaped_text = re.sub(r'\\\*\\\*', '**', escaped_text)
		return escaped_text
	except Exception as e:
		return str(e)
