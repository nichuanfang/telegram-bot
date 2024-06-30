import io
import platform
import re
import aiohttp
from bots.gpt_bot.gpt_platform import gpt_platform
from bots.gpt_bot.gpt_platform import Platform
from fake_useragent import UserAgent
from telegram.ext import CallbackContext
import orjson
from my_utils.my_logging import get_logger

ua = UserAgent(browsers="chrome")
pattern = re.compile(r'(?<=data: )(.*?)(?=\r?\n)')
HTTP_PROXY = 'http://127.0.0.1:10809' if platform.system().lower() == 'windows' else None
logger = get_logger('free_3')


@gpt_platform
class Free_3(Platform):

    async def query_balance(self):
        """
        查询余额
        @return: 
        """
        return '已使用 $0.0 , 订阅总额 $0.0'

    async def completion(self, stream: bool, context: CallbackContext, *messages, **kwargs):
        new_messages, kwargs = self.chat.combine_messages(
            *messages, **kwargs)
        answer = ''
        try:
            session = aiohttp.ClientSession()
            if stream:
                json_data = {
                    'stream': True,
                    'messages': new_messages,
                    'max_tokens': 16000,
                    'model': kwargs['model']
                }
                headers = {
                    'origin': self.foreign_openai_base_url,
                    'user-agent': ua.random,
                    'authorization': self.openai_api_key,
                }
                async with session.post(f'{self.foreign_openai_base_url}/api/chat/completions', headers=headers, json=json_data, proxy=HTTP_PROXY) as response:
                    response.raise_for_status()  # 检查请求是否成功
                    answer_parts = []
                    buffer = bytearray()
                    incomplete_line = ''
                    async for item in response.content.iter_any():
                        # 将每个字节流写入缓冲区
                        buffer.extend(item)
                        try:
                            content = buffer.decode()
                        except UnicodeDecodeError:
                            continue
                        lines = content.splitlines()
                        for line in lines:
                            if line:
                                if '[DONE]' in line:
                                    yield 'finished', answer
                                    break
                                else:
                                    try:
                                        delta = orjson.loads(line[6:])[
                                            'choices'][0]['delta']
                                        if delta:
                                            answer_parts.append(
                                                delta['content'])
                                            # 在需要时进行拼接
                                            answer = ''.join(answer_parts)
                                            yield 'not_finished', answer
                                        incomplete_line = ''
                                    except:
                                        incomplete_line = line
                        # 清空缓冲区
                        buffer.clear()
                        if incomplete_line:
                            buffer.extend(incomplete_line.encode())
            else:
                json_data = {
                    'stream': False,
                    'messages': new_messages,
                    'max_tokens': 16000,
                    'model': kwargs['model']
                }
                headers = {
                    'origin': self.foreign_openai_base_url,
                    'user-agent': ua.random,
                    'authorization': self.openai_api_key
                }
                async with session.post(f'{self.foreign_openai_base_url}/api/chat/completions', headers=headers, json=json_data, proxy=HTTP_PROXY) as response:
                    response.raise_for_status()  # 检查请求是否成功
                    completion = await response.text()
                    result = []
                    for line in completion.splitlines():
                        if line or line != 'data: [DONE]':
                            delta = orjson.loads(line[6:])[
                                'choices'][0]['delta']
                            if delta:
                                result.append(delta['content'])
                    answer = ''.join(result)
                    yield answer
        finally:
            if session:
                await session.close()
        await self.chat.append_messages(
            answer, context, *messages)

    async def summary(self, content: dict, prompt: str):
        new_messages = [{'role': 'system', 'content': prompt}, content]
        json_data = {
            'stream': True,
            'messages': new_messages,
            'max_tokens': 16000,
            'model': 'gpt-4o'
        }
        headers = {
            'origin': self.foreign_openai_base_url,
            'user-agent': ua.random,
            'authorization': self.openai_api_key
        }
        try:
            session = aiohttp.ClientSession()
            async with session.post(f'{self.foreign_openai_base_url}/api/chat/completions', headers=headers, json=json_data, proxy=HTTP_PROXY) as response:
                response.raise_for_status()  # 检查请求是否成功
                completion = await response.text()
                result = []
                for line in completion.splitlines():
                    if line or line != 'data: [DONE]':
                        try:
                            delta = orjson.loads(line[6:])[
                                'choices'][0]['delta']
                        except:
                            continue
                        if delta:
                            result.append(delta['content'])
                return ''.join(result)
        finally:
            if session:
                await session.close()
