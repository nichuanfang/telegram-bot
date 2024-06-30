import asyncio
import atexit
import base64
import datetime
import functools
import importlib
import orjson
import os
import re
from redis import ConnectionPool
import requests
from urllib.parse import urlparse
import uuid

from fake_useragent import UserAgent
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext
from bots.gpt_bot.gpt_platform import Platform
from my_utils import redis_util
from my_utils.my_logging import get_logger
from my_utils.validation_util import validate
ua = UserAgent()

logger = get_logger('bot_util')
# 临时配置路径
TEMP_CONFIG_PATH = os.path.join('temp', 'config.json')
# 代码分享平台的地址
HASTE_SERVER_HOST = os.getenv('HASTE_SERVER_HOST', None)
if not HASTE_SERVER_HOST:
    raise ValueError('请配置代码分享平台的地址!')
# ====================================加载面具================================
masks_path = os.path.abspath(os.path.join(
    'bots', 'gpt_bot', 'config', 'masks.json'))
# 加载面具
with open(masks_path, encoding='utf-8') as masks_file:
    masks = orjson.loads(masks_file.read())
# ====================================注册平台================================

platforms_path = os.path.abspath(os.path.join(
    'bots', 'gpt_bot', 'config', 'platforms.json'))
if os.path.exists(platforms_path):
    with open(platforms_path, encoding='utf-8') as platforms_file:
        platforms = orjson.loads(platforms_file.read())
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


def platform_default_mask():
    """平台默认面具
    """
    default_platform: dict = platforms[DEFAULT_PLATFORM_KEY]
    # 支持的面具
    supported_masks = default_platform['supported_masks']
    return masks[supported_masks[0]]


def platform_default_model():
    """平台默认模型
    """
    default_platform: dict = platforms[DEFAULT_PLATFORM_KEY]
    # 支持的面具
    supported_masks = default_platform['supported_masks']
    # 模型面具映射表
    mask_model_mapping = default_platform['mask_model_mapping']
    return mask_model_mapping[supported_masks[0]][0]


def instantiate_platform(platform_key: str = DEFAULT_PLATFORM_KEY, need_logger: bool = False):
    """
    初始化平台
    @param platform_name: 平台名称(英文)
    @param   max_message_count 最大消息数
    @return:  平台对象
    """
    # 默认平台
    platform = platforms[platform_key]

    # 如果没配置openai_api_key 说明是free_3/4 需要爬虫抓取授权码
    if 'openai_api_key' not in platform:
        # 反序列化平台信息
        platform: dict = generate_api_key(platform)
        openai_api_key = platform['openai_api_key']
    else:
        openai_api_key = platform['openai_api_key']
    default_mask = platform['supported_masks'][0]
    # 平台初始化参数
    platform_init_params = {
        'name': platform_key,
        'name_zh': platform['name'],
        'domestic_openai_base_url': platform['domestic_openai_base_url'],
        'foreign_openai_base_url': platform['foreign_openai_base_url'],
        'openai_api_key': openai_api_key,
        'index_url': platform['index_url'],
        'payment_url': platform['payment_url'],
        'max_message_count': masks[default_mask]['max_message_count'],
        'supported_models': platform['supported_models'],
        'supported_masks': platform['supported_masks'],
        'mask_model_mapping': platform['mask_model_mapping']
    }
    if need_logger:
        logger.info(f'当前使用的openai代理平台为{platform["name"]}.')
    return PLATFORMS_REGISTRY[platform_key](**platform_init_params)


async def migrate_platform(from_platform: Platform, to_platform_key: str, context: CallbackContext, max_message_count: int):
    """
    迁移平台
    @param from_platform 原平台对象
    @param to_platform_key: 要迁移到的平台key
    @param current_model: 当前的模型
    @param   max_message_count 最大消息数
    @return:  平台对象
    """
    # 迁移到的平台
    to_platform: dict = platforms[to_platform_key]

    # 如果没配置openai_api_key 说明是free_3/4
    if 'openai_api_key' not in to_platform:
        to_platform: dict = generate_api_key(to_platform)
        openai_api_key = to_platform['openai_api_key']
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
        'max_message_count': max_message_count,
        'supported_models': to_platform['supported_models'],
        'supported_masks': to_platform['supported_masks'],
        'mask_model_mapping': to_platform['mask_model_mapping']
    }
    logger.info(f'当前使用的openai代理平台为{to_platform["name"]}.')
    # 新平台
    new_platform: Platform = PLATFORMS_REGISTRY[to_platform_key](
        **platform_init_params)
    # 恢复历史消息
    new_platform.chat._messages.core = from_platform.chat._messages.core
    # 修剪历史消息
    new_platform.chat.clear_messages(context)
    return new_platform


# =====================================授权相关====================================
values = validate('ALLOWED_TELEGRAM_USER_IDS')
# 允许访问的用户列表 逗号分割并去除空格
ALLOWED_TELEGRAM_USER_IDS = [user_id.strip()
                             for user_id in values[0].split(',')]


# Redis连接池用于存储每日访问计数和过期时间
REDIS_POOL: ConnectionPool = redis_util.create_redis_pool()
# 注册关闭连接池
atexit.register(lambda: asyncio.run(redis_util.close_redis_pool(REDIS_POOL)))


def check_visitor_quota(user_id):
    today_date = datetime.date.today()
    redis_key = f"visitor_quota:{user_id}:{today_date}"

    if REDIS_POOL is None:
        raise RuntimeError("Redis pool is not initialized.")

    with redis_util.get_redis_client(REDIS_POOL) as redis_client:
        # 获取当前用户今天的访问次数
        count = redis_util.get(redis_client, redis_key)
        if count is None:
            count = 0
        else:
            count = int(count)

        # 访客每天最多100次调用
        if count >= 100:
            return False

        # 访问次数加1，并设置过期时间为今天的最后一秒钟
        count += 1
        # 设置过期时间为一天(86400秒)
        redis_util.set(redis_client, redis_key, count, expire=86400)

    return True


def auth(func):
    """ 自定义授权装饰器 """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        update: Update = args[0]
        context: CallbackContext = args[1]
        user_id = update.effective_user.id

        if 'identity' not in context.user_data:
            if str(user_id) not in ALLOWED_TELEGRAM_USER_IDS:
                context.user_data['identity'] = 'visitor'
                # 检查访客的每日访问次数是否超限
                if not check_visitor_quota(user_id):
                    await update.message.reply_text('Exceeded daily visitor quota. Access denied.')
                    return
            else:
                context.user_data['identity'] = 'user'

            if context.bot.first_name == 'GPTBot':
                context.user_data['current_platform'] = instantiate_platform(
                    need_logger=True)
                context.user_data['candidate_platform'] = instantiate_platform(
                    platform_key='free_1', need_logger=False)
                context.user_data['current_mask'] = platform_default_mask()
                context.user_data['current_model'] = platform_default_model()
        else:
            if context.user_data['identity'] == 'visitor':
                # 检查访客的每日访问次数是否超限
                if not check_visitor_quota(user_id):
                    await update.message.reply_text('Exceeded daily visitor quota. Access denied.')
                    return

        await func(*args, **kwargs)

    return wrapper


def generate_api_key(platform: dict):
    # 尝试先从临时配置文件获取
    if os.path.exists(TEMP_CONFIG_PATH):
        with open(TEMP_CONFIG_PATH, mode='r', encoding='utf-8') as f:
            temp_config_data: dict = orjson.loads(f.read())
            #   配置文件键为平台key  值为 授权码/认证信息
            if platform['platform_key'] in temp_config_data and 'openai_api_key' in temp_config_data[platform['platform_key']]:
                return temp_config_data[platform['platform_key']]
    # 扩展性配置  免费节点的特殊操作
    if platform['platform_key'] == 'free_3':
        return generate_authorization(platform)
    elif platform['platform_key'] == 'free_4':
        return generate_authorization(platform)
    # elif platform['platform_key'] == 'free_1':
    #     return generate_code(platform)


def generate_code(platform: dict):
    """
    生成授权码  (用户名密码获取地址   https://free01.xyz)
    @param platform: 平台
    @return: 授权码
    """
    url = platform['index_url']
    parsed_url = urlparse(url)
    headers = {
        'origin': f'{parsed_url.scheme}://{parsed_url.netloc}',
        'user-agent': ua.random,
        'Authorization': f'Basic {base64.b64encode(( platform["username"] + ":" + platform["password"]).encode()).decode()}'
    }
    response = requests.get(platform['index_url'], headers=headers)
    html_content = response.content.decode('utf-8')
    # 定义正则表达式模式
    pattern = r"密码：\s*(\d+)"
    url_pattern = r'href="(https?://[^"]+)"'
    # 使用正则表达式查找密码
    password_matches = re.findall(pattern, html_content)
    url_matches = re.findall(url_pattern, html_content)
    if len(password_matches) == 0 or len(url_matches) == 0:
        url = platform['reveal _url']
        code = platform['reveal_code']
    else:
        url = url_matches[0] if url_matches[0].endswith(
            '/') else url_matches[0] + '/'
        code = password_matches[0]
    platform['domestic_openai_base_url'] = f'{url}api/openai/v1'
    platform['foreign_openai_base_url'] = f'{url}api/openai/v1'
    platform['openai_api_key'] = f'nk-{code}'

    if os.path.exists(TEMP_CONFIG_PATH):
        with open(TEMP_CONFIG_PATH, mode='r', encoding='utf-8') as f:
            old_json_data: dict = orjson.loads(f.read())
    else:
        old_json_data = {}

    # 刷新临时配置文件
    with open(TEMP_CONFIG_PATH, mode='w+', encoding='utf-8') as f:
        old_json_data.update({
            platform['platform_key']: platform
        })
        f.write(orjson.dumps(old_json_data, option=orjson.OPT_INDENT_2).decode())
    return platform


# def generate_cf_authorization(platform: dict):
#     """ 既要生成认证头 也要生成cf_cookie 还要保存对应的user-agent  open_api_key是个字典
#     Args:
#         platform (_type_):  平台元信息
#     """
#     url = platform['foreign_openai_base_url']
#     # 构建user_agent和cf_clearance   如果状态码是500 跳过
#     with CFSession.cfSession(headless_mode=True) as session:
#         parsed_url = urlparse(url)
#         email = platform['email']
#         password = platform['password']
#         headers = {
#             'origin': f'{parsed_url.scheme}://{parsed_url.netloc}',
#             'content-type': 'application/json'
#         }
#         response = session.post(f'{url}/api/v1/auths/signin', json={
#             'email': email,
#             'password': password,
#         }, headers=headers)
#     if response.status_code == 200:
#         json_data = orjson.loads(response.text)
#         token = json_data['token']
#         token_type = json_data['token_type']
#         platform['openai_api_key'] = f'{token_type} {token}'
#         if os.path.exists(TEMP_CONFIG_PATH):
#             with open(TEMP_CONFIG_PATH, mode='r', encoding='utf-8') as f:
#                 old_json_data: dict = orjson.loads(f.read())
#         else:
#             old_json_data = {}

#         # 刷新临时配置文件
#         with open(TEMP_CONFIG_PATH, mode='w+', encoding='utf-8') as f:
#             old_json_data.update({
#                 platform['platform_key']:  platform
#             })
#             f.write(orjson.dumps(old_json_data,
#                     option=orjson.OPT_INDENT_2).decode())
#         return platform
#     else:
#         raise RuntimeError('生成free_3的token失败!')


def generate_authorization(platform: dict):
    """生成认证头

    Args:
        platform (_type_):  平台元信息
    """
    url = platform['foreign_openai_base_url']
    parsed_url = urlparse(url)
    email = platform['email']
    password = platform['password']
    headers = {
        'origin': f'{parsed_url.scheme}://{parsed_url.netloc}',
        'user-agent': ua.random,
        'content-type': 'application/json'
    }
    response = requests.post(f'{url}/api/v1/auths/signin', json={
        'email': email,
        'password': password,
    }, headers=headers)
    if response.status_code == 200:
        json_data = orjson.loads(response.text)
        token = json_data['token']
        token_type = json_data['token_type']
        platform['openai_api_key'] = f'{token_type} {token}'

        if os.path.exists(TEMP_CONFIG_PATH):
            with open(TEMP_CONFIG_PATH, mode='r', encoding='utf-8') as f:
                old_json_data: dict = orjson.loads(f.read())
        else:
            old_json_data = {}

        # 刷新临时配置文件
        with open(TEMP_CONFIG_PATH, mode='w+', encoding='utf-8') as f:
            old_json_data.update({
                platform['platform_key']:  platform
            })
            f.write(orjson.dumps(old_json_data,
                    option=orjson.OPT_INDENT_2).decode())
        return platform
    else:
        # 保持原认证信息不变
        raise Exception('刷新认证信息失败!')

# =====================================消息相关====================================


async def send_message(update: Update, text):
    try:
        escaped_text = escape_markdown_v2(text)  # 转义特殊字符
        return await update.message.reply_text(escaped_text,
                                               reply_to_message_id=update.message.message_id,
                                               disable_web_page_preview=True,
                                               parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        # 如果格式化错误 就发送到代码分享平台
        response = requests.post(
            f'{HASTE_SERVER_HOST}/documents', data=text.encode('utf-8'))
        if response.status_code == 200:
            result = response.json()
            document_id = result.get('key')
            if document_id:
                document_url = f'{HASTE_SERVER_HOST}/raw/{document_id}.md'
                await update.message.reply_text(f'{text}\n\n请访问：{document_url}')
            else:
                await update.message.reply_text(text)


async def edit_message(update: Update, context: CallbackContext, message_id, stream_ended, text):
    try:
        # 等流式响应完全结束再尝试markdown格式 加快速度
        if stream_ended:
            if text:
                # 如果格式话前的文本和之后的文本一模一样
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
                    text='Empty  Content!',
                    chat_id=update.message.chat_id,
                    message_id=message_id,
                    disable_web_page_preview=True
                )
                context.user_data['current_platform'].chat.clear_messages(
                    context)
        else:
            await context.bot.edit_message_text(
                text=text,
                chat_id=update.message.chat_id,
                message_id=message_id,
                disable_web_page_preview=True
            )
    except Exception as e:
        if 'Message is not modified' in e.message:
            await context.bot.edit_message_text(
                text=escaped_text+'🔚',
                chat_id=update.message.chat_id,
                message_id=message_id,
                disable_web_page_preview=True,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            # 如果格式化错误 就发送到代码分享平台
            response = requests.post(
                f'{HASTE_SERVER_HOST}/documents', data=text.encode('utf-8'))
            if response.status_code == 200:
                result = response.json()
                document_id = result.get('key')
                if document_id:
                    document_url = f'{HASTE_SERVER_HOST}/raw/{document_id}.md'
                    await context.bot.edit_message_text(
                        text=f'{text}\n\n请访问：{document_url}',
                        chat_id=update.message.chat_id,
                        message_id=message_id,
                        disable_web_page_preview=True
                    )
                else:
                    await context.bot.edit_message_text(
                        text=text,
                        chat_id=update.message.chat_id,
                        message_id=message_id,
                        disable_web_page_preview=True
                    )


async def send_typing(update: Update):
    if update.message is not None:
        await update.message.reply_chat_action(action='typing')


async def send_typing_action(update: Update, context: CallbackContext, flag_key):
    if context.user_data is not None:
        while context.user_data.get(flag_key, False):
            if update.message is not None:
                await update.message.reply_chat_action(action='typing')
            await asyncio.sleep(3)  # 每3秒发送一次 typing 状态


def escape_markdown_v2(text: str, need_format_asterisk: bool = True) -> str:
    """
    Escape special characters for Telegram MarkdownV2 and replace every pair of consecutive asterisks (**) with a single asterisk (*).
    """
    try:
        escape_chars = r'\_[]()~>#+-=|{}.!'
        escaped_text = re.sub(f"([{re.escape(escape_chars)}])", r'\\\1', text)
        # 格式化其它列表语法
        if need_format_asterisk:
            escaped_text = re.sub(r'(?<!\*)\*(?!\*)', '\*', escaped_text)
        # escaped_text = re.sub(r'(?<!\`)\`(?!\`)', '\`', escaped_text)
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
