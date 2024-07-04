import asyncio
import io
import platform
import re
import aiohttp
from bots.gpt_bot.core.session import SessionWithRetry
from bots.gpt_bot.core.streaming import SSE_DECODER
from bots.gpt_bot.gpt_platform import gpt_platform
from bots.gpt_bot.gpt_platform import Platform
from telegram.ext import CallbackContext
from my_utils import bot_util, code_util, tiktoken_util
import orjson


from my_utils.my_logging import get_logger
pattern = re.compile(r'(?<=data: )(.*?)(?=\r?\n)')
image_pattern = re.compile(r'\!\[Image\]\((.*?)\)')
HTTP_PROXY = 'http://127.0.0.1:10809' if platform.system().lower() == 'windows' else None
logger = get_logger('free_4')


def extract_image_url(text):
    # 正则表达式匹配 ![Image](URL) 格式的字符串
    match = image_pattern.search(text)
    if match:
        return match.group(1)  # 返回匹配到的 URL 部分
    else:
        raise RuntimeError(text)


@gpt_platform
class Free_4(Platform):

    async def query_balance(self):
        """
        查询余额
        @return: 
        """
        return '已使用 $0.0 , 订阅总额 $0.0'

    async def generate_image(self, messages: list, context: CallbackContext, session: aiohttp.ClientSession):
        # 生成图片
        json_data = {
            'stream': True,
            'messages': messages,
            'model': 'gpt-3.5-turbo'
        }
        headers = {
            'origin': self.foreign_openai_base_url,
            'user-agent': bot_util.ua.random,
            'authorization': self.openai_api_key
        }
        answer = ''
        async for answer in SessionWithRetry(session, context).post(f'{self.foreign_openai_base_url}/openai/chat/completions', headers=headers, json=json_data):
            return extract_image_url(answer)

    async def completion(self, stream: bool, context: CallbackContext, session: aiohttp.ClientSession, *messages):
        openai_completion_options = context.user_data['current_mask']['openai_completion_options']
        new_messages, openai_completion_options = self.chat.combine_messages(
            *messages, **openai_completion_options)
        json_data = {
            'stream': stream,
            'messages': new_messages,
            'model': context.user_data['current_model'],
            'temperature': openai_completion_options['temperature'],
            'top_p': openai_completion_options['top_p']
        }
        headers = {
            'origin': self.foreign_openai_base_url,
            'user-agent': bot_util.ua.random,
            'authorization': self.openai_api_key
        }
        async for result in SessionWithRetry(session, context).post(f'{self.foreign_openai_base_url}/api/chat/completions', headers=headers, json=json_data, stream=stream):
            yield result
        await self.chat.append_messages(
            result[1] if isinstance(result, tuple) else result, context, *messages)

    async def summary(self, content: str, prompt: str, context, *messages):
        new_messages = [{'role': 'system', 'content': prompt},
                        {'role': 'user', 'content': content}]
        json_data = {
            'stream': True,
            'messages': new_messages,
            'model': 'gpt-4o'
        }
        headers = {
            'origin': self.foreign_openai_base_url,
            'user-agent': bot_util.ua.random,
            'authorization': self.openai_api_key
        }
        try:
            async with aiohttp.ClientSession(raise_for_status=True, trust_env=True, timeout=aiohttp.ClientTimeout(total=30)) as session:
                async for summary in SessionWithRetry(session, context).post(f'{self.foreign_openai_base_url}/openai/chat/completions', headers=headers, json=json_data):
                    answer = summary
        except:
            answer = content

        await self.chat.append_messages(
            answer, context, *messages)
