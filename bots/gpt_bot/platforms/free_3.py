import json
import requests
from bots.gpt_bot.gpt_http_request import HTTP_CLIENT
from bots.gpt_bot.gpt_platform import gpt_platform
from bots.gpt_bot.gpt_platform import Platform
from fake_useragent import UserAgent

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


@gpt_platform
class Free_3(Platform):

    async def query_balance(self):
        """
        查询余额
        @return: 
        """
        return '已使用 $0.0 , 订阅总额 $0.0'

    async def completion(self, stream: bool, context, *messages, **kwargs):
        # 默认的提问方法
        new_messages, kwargs = self.chat.combine_messages(*messages, **kwargs)
        if stream:
            json_data = {
                'stream': True,
                'messages': new_messages,
                'citations': False,
                "chat_id": "b0ade8ce-9f70-4fab-ac89-768d7d443d9",
                **kwargs
            }
            headers.update({
                'origin': self.foreign_openai_base_url,
                'user-agent': ua.random,
                'authorization': self.openai_api_key
            })

            with requests.get(f'{self.foreign_openai_base_url}/openai/chat/completions', headers=headers, json=json_data, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        # 假设API返回的是JSON格式数据
                        data = json.loads(line.decode('utf-8'))
                        # 在这里处理接收到的数据
                        print(data)  # 举例输出，根据实际情况进行处理
            answer: str = ""
            # async for chunk_iter in completion:
            #     if chunk_iter.choices and (chunk := chunk_iter.choices[0].delta.content):
            #         answer += chunk
            #         yield 'not_finished', answer
            # yield 'finished', answer
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
            answer = json.loads(completion.text)[
                'choices'][0]['message']['content']
            yield answer
        await self.chat.append_messages(
            answer, context, *messages)
