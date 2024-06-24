import ujson
import requests
from bots.gpt_bot.gpt_platform import gpt_platform
from bots.gpt_bot.gpt_platform import Platform
from fake_useragent import UserAgent

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
logger = get_logger('free_3')

pattern = r'"content":"([^"]*)"'


@gpt_platform
class Free_3(Platform):

    async def query_balance(self):
        """
        查询余额
        @return: 
        """
        return '已使用 $0.0 , 订阅总额 $0.0'

    async def completion(self, stream: bool, context, *messages, **kwargs):
        kwargs['messages'][0]['content'] = kwargs['messages'][0]['content']+',请用中文进行回复'
        # 默认的提问方法
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
            with requests.post(
                    f'{self.foreign_openai_base_url}/openai/chat/completions', headers=headers, json=json_data, stream=True) as response:
                for line in response.iter_lines():
                    raw_data = line.decode('utf-8')[6:]
                    if raw_data == '[DONE]':
                        yield 'finished', answer
                        break
                    if raw_data:
                        try:
                            data = ujson.loads(raw_data)
                        except:
                            raise RuntimeError(raw_data)
                        delta = data['choices'][0]['delta']
                        if 'content' in delta:
                            answer += delta['content']
                        yield 'not_finished', answer

        else:
            # todo 此平台的图片解析有问题 需要研究
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
            completion = requests.post(
                f'{self.foreign_openai_base_url}/openai/chat/completions', headers=headers, json=json_data)
            try:
                answer = ujson.loads(completion.text)[
                    'choices'][0]['message']['content']
                yield answer
            except:
                raise RuntimeError(completion.text)
        await self.chat.append_messages(
            answer, context, *messages)
