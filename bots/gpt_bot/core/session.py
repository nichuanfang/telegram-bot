from types import coroutine
from typing import Callable, Coroutine, Dict
import aiohttp
import asyncio
from aiohttp import hdrs
from aiohttp import ClientResponse
from aiohttp.client import _RequestContextManager
import orjson
from bots.gpt_bot.gpt_platform import Platform
from my_utils import bot_util
from my_utils.my_logging import get_logger
from telegram.ext import CallbackContext


logger = get_logger('gpt-session')


async def reauth(current_platform: Platform, context: CallbackContext):
    """ 重新认证 """
    json_data = None
    with open(bot_util.TEMP_CONFIG_PATH, mode='r', encoding='utf-8') as f:
        json_data: dict = orjson.loads(f.read())
        if current_platform.name in json_data:
            if 'openai_api_key' in json_data[current_platform.name]:
                json_data[current_platform.name].pop('openai_api_key')
    if json_data:
        with open(bot_util.TEMP_CONFIG_PATH, mode='w+', encoding='utf-8') as f:
            f.write(orjson.dumps(json_data).decode())
            # 刷新token成功!
    current_platform = context.user_data['current_platform'] = await bot_util.instantiate_platform(platform_key=current_platform.name)
    return current_platform


async def handle_unauthorized_error(e: Exception, context: CallbackContext, **kwargs):
    """ 处理未授权 """
    # 当前平台
    current_platform: Platform = context.user_data['current_platform']
    if current_platform.name.startswith('free'):
        # free_3/4    可能授权码/认证信息失效了
        current_platform = await reauth(current_platform, context)
        kwargs['headers']['authorization'] = current_platform.openai_api_key
    else:
        # 非免费平台 可能就是单纯的key余额不足
        raise e


async def handle_service_unavailable(e: Exception, context: CallbackContext, **kwargs):
    """ 处理服务不可达 """
    # 当前平台
    # current_platform: Platform = context.user_data['current_platform']
    pass


async def handle_server_internal_error(e: Exception, context: CallbackContext, **kwargs):
    """ 处理服务器内部错误 """
    # 当前平台
    current_platform: Platform = context.user_data['current_platform']
    if current_platform.name.startswith(('free_3', 'free_4')):
        # 可能是授权失效了
        current_platform = await reauth(current_platform, context)
        kwargs['headers']['authorization'] = current_platform.openai_api_key


class SessionWithRetry:

    def __init__(self, session: aiohttp.ClientSession, context: CallbackContext, retry_attempts: int = 3, retry_interval: float = 2.0,
                 conditions_handlers: Dict[Callable[[Exception], bool], Coroutine[None, Exception, None]] = None):
        """ 会话增强-自动重试 """
        # 会话对象
        self.session = session
        # telegram的上下文对象
        self.context = context
        # 重试次数
        self.retry_attempts = retry_attempts
        # 重试间隔
        self.retry_interval = retry_interval
        # 条件处理器映射 注册几个默认的  不要配置重复条件 因为只会后面的条件可能得不到执行机会!
        self.conditions_handlers = conditions_handlers or {
            lambda e: e.status == 403: handle_unauthorized_error,
            lambda e: e.status == 500: handle_server_internal_error,
            lambda e: e.status == 503: handle_service_unavailable,
        }

    async def fetch_with_retry(self, method: str, url: str, **kwargs) -> ClientResponse:
        attempt = 0
        while attempt < self.retry_attempts:
            try:
                return await getattr(self.session, '_request')(method, url, allow_redirects=True, **kwargs)
            except Exception as e:
                should_retry = False
                for condition, handler in self.conditions_handlers.items():
                    if condition(e):
                        try:
                            # 尝试处理器
                            await handler(e, self.context, **kwargs)
                            should_retry = True
                            # 隔几秒后重新发起请求
                            await asyncio.sleep(self.retry_interval)
                            break
                        except Exception as handler_exception:
                            # 异常处理器方法报错 放弃重试
                            raise handler_exception
                if not should_retry:
                    # 如果没有满足条件的处理器则直接抛出异常
                    raise e

            attempt += 1

        # 如果尝试次数已用尽，抛出异常
        raise Exception(
            f"Failed to fetch {url} after {self.retry_attempts} attempts")

    def post(self, url: str, **kwargs):
        return _RequestContextManager(self.fetch_with_retry(hdrs.METH_POST, url, **kwargs))

    def get(self, url: str, **kwargs):
        return _RequestContextManager(self.fetch_with_retry(hdrs.METH_GET, url, **kwargs))
