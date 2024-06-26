import platform
import re
import aiohttp
import ujson
from bots.gpt_bot.gpt_platform import gpt_platform
from bots.gpt_bot.gpt_platform import Platform
from fake_useragent import UserAgent
from telegram.ext import CallbackContext


from my_utils.my_logging import get_logger

headers = {
    'accept': '*/*',
    'accept-language': 'zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7,ja;q=0.6',
    'priority': 'u=1, i',
    'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
}
ua = UserAgent()
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

    async def generate_image(self, messages: list):
        # 生成图片
        json_data = {
            'stream': True,
            'messages': messages,
            'citations': False,
            'model': 'gpt-3.5-turbo'
        }
        headers.update({
            'origin': self.foreign_openai_base_url,
            'user-agent': ua.random,
            'authorization': self.openai_api_key
        })
        answer = ''
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{self.foreign_openai_base_url}/openai/chat/completions', headers=headers, json=json_data, proxy=HTTP_PROXY) as response:
                response.raise_for_status()  # 检查请求是否成功
                async for item in response.content.iter_any():
                    try:
                        chunks = item.decode().splitlines()
                        for chunk in chunks:
                            if chunk:
                                raw_data = chunk[6:]
                                if raw_data == '[DONE]':
                                    break
                                else:
                                    delta = ujson.loads(raw_data)[
                                        'choices'][0]['delta']
                                    if delta:
                                        answer += delta['content']
                    except:
                        continue
        return extract_image_url(answer)

    async def completion(self, stream: bool, context: CallbackContext, *messages, **kwargs):
        new_messages, kwargs = self.chat.combine_messages(
            *messages, **kwargs)
        answer = ''
        if stream:
            json_data = {
                'stream': True,
                'messages': new_messages,
                'citations': False,
                **kwargs
            }
            headers.update({
                'origin': self.foreign_openai_base_url,
                'user-agent': ua.random,
                'authorization': self.openai_api_key
            })

            async with aiohttp.ClientSession() as session:
                async with session.post(f'{self.foreign_openai_base_url}/openai/chat/completions', headers=headers, json=json_data, proxy=HTTP_PROXY) as response:
                    response.raise_for_status()  # 检查请求是否成功
                    async for item in response.content.iter_any():
                        try:
                            chunks = item.decode().splitlines()
                            for chunk in chunks:
                                if chunk:
                                    raw_data = chunk[6:]
                                    if raw_data == '[DONE]':
                                        yield 'finished', answer
                                        break
                                    else:
                                        delta = ujson.loads(raw_data)[
                                            'choices'][0]['delta']
                                        if delta:
                                            answer += delta['content']
                                            yield 'not_finished', answer
                        except:
                            continue
            await self.chat.append_messages(answer, context, *messages)

        else:
            json_data = {
                'stream': False,
                'messages': new_messages,
                'citations': False,
                **kwargs
            }
            headers.update({
                'origin': self.foreign_openai_base_url,
                'user-agent': ua.random,
                'content-type': 'application/json',
                'authorization': self.openai_api_key
            })
            async with aiohttp.ClientSession() as session:
                async with session.post(f'{self.foreign_openai_base_url}/openai/chat/completions', headers=headers, json=json_data, proxy=HTTP_PROXY) as response:
                    response.raise_for_status()  # 检查请求是否成功
                    completion = await response.json()
                    answer = completion[
                        'choices'][0]['message']['content']
                    yield answer
        await self.chat.append_messages(
            answer, context, *messages)
