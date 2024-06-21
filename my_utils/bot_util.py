import asyncio
import base64
import functools
import importlib
import json
import os
import re
import uuid

import requests
from fake_useragent import UserAgent
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext
from bots.gpt_bot.gpt_platform import Platform
from my_utils.my_logging import get_logger
from my_utils.validation_util import validate
logger = get_logger('bot_util')
# 代码分享平台的地址
HASTE_SERVER_HOST = os.getenv('HASTE_SERVER_HOST', None)
if not HASTE_SERVER_HOST:
    raise ValueError('请配置代码分享平台的地址!')
# ====================================加载面具================================
# 默认面具
DEFAULT_MASK_KEY: str = os.getenv('DEFAULT_MASK_KEY', 'common')
masks_path = os.path.abspath(os.path.join(
    'bots', 'gpt_bot', 'config', 'masks.json'))
# 加载面具
with open(masks_path, encoding='utf-8') as masks_file:
    masks = json.load(masks_file)
# ====================================注册平台================================

platforms_path = os.path.abspath(os.path.join(
    'bots', 'gpt_bot', 'config', 'platforms.json'))
if os.path.exists(platforms_path):
    with open(platforms_path, encoding='utf-8') as platforms_file:
        platforms = json.load(platforms_file)
else:
    raise RuntimeError('platforms.json不存在,无法加载平台数据!')

# 默认平台
DEFAULT_PLATFORM_KEY: str = os.getenv('DEFAULT_PLATFORM_KEY', 'free_1')
# 模型注册表
PLATFORMS_REGISTRY = {}
platforms_path = os.path.abspath(os.path.join('bots', 'gpt_bot', 'platforms'))
for file in os.listdir(platforms_path):
    if not file.endswith('.py'):
        continue
    name = file.split(".")[0]
    platform_module = importlib.import_module(f'bots.gpt_bot.platforms.{name}')
    for attr_name in dir(platform_module):
        attr = getattr(platform_module, attr_name)
        if isinstance(attr, type) and getattr(attr, '_is_gpt_platform', False):
            platform_key = attr._platform_key()
            PLATFORMS_REGISTRY[platform_key] = attr


def instantiate_platform():
    """
    初始化平台
    @param platform_name: 平台名称(英文)
    @param   max_message_count 最大消息数
    @return:  平台对象
    """
    # 默认平台
    platform = platforms[DEFAULT_PLATFORM_KEY]

    # 如果没配置openai_api_key 说明是free_1 需要爬虫抓取授权码  构造成 'Bearer nk-{code} 这样的授权头
    if 'openai_api_key' not in platform:
        try:
            url, code = generate_code(
                platform['index_url'], platform['username'], platform['password'])
        except:
            # 兜底url和code 防止发布站不可用 获取不到目标网站信息
            url = platform['reveal _url']
            code = platform['reveal_code']
        platform['domestic_openai_base_url'] = f'{url}api/openai/v1'
        platform['foreign_openai_base_url'] = f'{url}api/openai/v1'
        openai_api_key = f'nk-{code}'
    else:
        openai_api_key = platform['openai_api_key']
    # 平台初始化参数
    platform_init_params = {
        'name': DEFAULT_PLATFORM_KEY,
        'name_zh': platform['name'],
        'domestic_openai_base_url': platform['domestic_openai_base_url'],
        'foreign_openai_base_url': platform['foreign_openai_base_url'],
        'openai_api_key': openai_api_key,
        'index_url': platform['index_url'],
        'payment_url': platform['payment_url'],
        'max_message_count': 4 if DEFAULT_PLATFORM_KEY.startswith('free') else masks[DEFAULT_MASK_KEY]['max_message_count']
    }
    logger.info(f'当前使用的openai代理平台为{platform["name"]}.')
    return PLATFORMS_REGISTRY[DEFAULT_PLATFORM_KEY](**platform_init_params)


def migrate_platform(from_platform: Platform, to_platform_key: str, max_message_count: int):
    """
    迁移平台
    @param from_platform 原平台对象
    @param to_platform_key: 要迁移到的平台key
    @param   max_message_count 最大消息数
    @return:  平台对象
    """
    # 迁移到的平台
    to_platform: dict = platforms[to_platform_key]

    # 如果没配置openai_api_key 说明是free_1 需要爬虫抓取授权码  构造成 'Bearer nk-{code} 这样的授权头
    if 'openai_api_key' not in to_platform:
        try:
            url, code = generate_code(
                to_platform['index_url'], to_platform['username'], to_platform['password'])
        except:
            url = to_platform['reveal _url']
            code = to_platform['reveal_code']
        to_platform['domestic_openai_base_url'] = f'{url}api/openai/v1'
        to_platform['foreign_openai_base_url'] = f'{url}api/openai/v1'
        openai_api_key = f'nk-{code}'
    else:
        openai_api_key = to_platform['openai_api_key']
    # 修改参数
    platform_init_params = {
        'name': to_platform_key,
        'name_zh': to_platform['name'],
        'domestic_openai_base_url': to_platform['domestic_openai_base_url'],
        'foreign_openai_base_url': to_platform['foreign_openai_base_url'],
        'openai_api_key': openai_api_key,
        'index_url': to_platform['index_url'],
        'payment_url': to_platform['payment_url'],
        'max_message_count': 4 if to_platform_key.startswith('free') else max_message_count
    }
    logger.info(f'当前使用的openai代理平台为{to_platform["name"]}.')
    # 新平台
    new_platform: Platform = PLATFORMS_REGISTRY[to_platform_key](
        **platform_init_params)
    # 恢复历史消息
    new_platform.chat._messages.core = from_platform.chat._messages.core
    # 修剪历史消息
    new_platform.chat._messages._trim()
    return new_platform


# =====================================授权相关====================================
values = validate('ALLOWED_TELEGRAM_USER_IDS')
# 允许访问的用户列表 逗号分割并去除空格
ALLOWED_TELEGRAM_USER_IDS = [user_id.strip()
                             for user_id in values[0].split(',')]


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
        if 'identity' not in context.user_data:
            if str(user_id) not in ALLOWED_TELEGRAM_USER_IDS:
                context.user_data['identity'] = 'vistor'
                # 只针对GBTBot开放访问 其他机器人正常拦截
                if context.bot.first_name == 'GPTBot':
                    logger.info(
                        f'=================user {user_id} access the GPTbot for free===================')
                    context.user_data['current_platform'] = instantiate_platform(
                    )
                else:
                    logger.warn(
                        f"======================user {user_id}'s  access has been filtered====================")
                    await update.message.reply_text('You are not authorized to use this bot.')
                    return
            else:
                if context.bot.first_name == 'GPTBot':
                    context.user_data['current_platform'] = instantiate_platform(
                    )
                context.user_data['identity'] = 'user'
        await func(*args, **kwargs)
    return wrapper


def generate_code(url: str, username: str, password: str):
    """
    构建授权码  (用户名密码获取地址   https://free01.xyz)
    @param url: 请求的url
    @param username: 白嫖发布站的用户名
    @param password: 白嫖发布站的密码
    @return: 授权码
    """
    ua = UserAgent()
    headers = {
        'user-agent': ua.random,
        'Authorization': f'Basic {base64.b64encode((username + ":" + password).encode()).decode()}'
    }
    response = requests.get(url, headers=headers)
    html_content = response.content.decode('utf-8')
    # 定义正则表达式模式
    pattern = r"密码：\s*(\d+)"
    url_pattern = r'href="(https?://[^"]+)"'
    # 使用正则表达式查找密码
    password_matches = re.findall(pattern, html_content)
    url_matches = re.findall(url_pattern, html_content)
    if len(password_matches) == 0:
        raise RuntimeError('free_1平台授权码提取失败!')
    if len(url_matches) == 0:
        raise RuntimeError('free_1平台授权码提取失败!')
    return url_matches[0] if url_matches[0].endswith('/') else url_matches[0] + '/', password_matches[0]


# =====================================消息相关====================================

async def send_message(update: Update, text):
    assert update.message
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
            chat_id = update.message.chat_id if update and update.message else None
            if chat_id is not None:
                await context.bot.edit_message_text(
                    text=escaped_text,
                    chat_id=chat_id,
                    message_id=message_id,
                    disable_web_page_preview=True,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        else:
            chat_id = update.message.chat_id if update and update.message else None
            if chat_id is not None:
                await context.bot.edit_message_text(
                    text=text,
                    chat_id=chat_id,
                    message_id=message_id,
                    disable_web_page_preview=True
                )
    except Exception:
        try:
            chat_id = update.message.chat_id if update and update.message else None
            if chat_id is not None:
                await context.bot.edit_message_text(
                    text=text,
                    chat_id=chat_id,
                    message_id=message_id, disable_web_page_preview=True)
        except Exception:
            pass


async def send_typing(update: Update):
    if update.message is not None:
        await update.message.reply_chat_action(action='typing')


async def send_typing_action(update: Update, context: CallbackContext, flag_key):
    if context.user_data is not None:
        while context.user_data.get(flag_key, False):
            if update.message is not None:
                await update.message.reply_chat_action(action='typing')
            await asyncio.sleep(3)  # 每3秒发送一次 typing 状态


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


# =====================================其他工具====================================

async def uuid_generator():
    while True:
        yield uuid.uuid4().__str__()


async def coroutine_wrapper(normal_function, *args, **kwargs):
    return await asyncio.to_thread(normal_function, *args, **kwargs)


async def async_func(normal_function, *args, **kwargs):
    return await coroutine_wrapper(normal_function, *args, **kwargs)
