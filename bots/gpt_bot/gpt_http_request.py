# 定制化请求

import requests
from fake_useragent import FakeUserAgent

headers = {
    'accept': 'application/json',
    'accept-language': 'zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7,ja;q=0.6',
    'priority': 'u=1, i',
    'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site'
}

# 随机ua
ua = FakeUserAgent(browsers="chrome", os='windows', platforms='pc')


class BotHttpRequest:

    @staticmethod
    async def audio_transcribe(file_path: str, openai_api_key: str, openai_base_url: str):
        headers['user-agent'] = ua.random
        headers['Authorization'] = f'Bearer {openai_api_key}'
        with open(file_path, 'rb') as file:
            files = {
                'file': (file_path, file, 'audio/wav')
            }
            data = {
                'model': 'whisper-1'
                # 'language': 'zh'
            }
            response = requests.post(
                url=f'{openai_base_url}/audio/transcriptions',
                files=files,
                data=data,
                headers=headers
            )
        if response.status_code == 200:
            return response.json()['text']
        else:
            raise RuntimeError(response.text)

    # 获取订阅
    @staticmethod
    async def get_subscription(openai_api_key: str, openai_base_url: str):
        # 生成一个随机的 User-Agent
        headers['user-agent'] = ua.random
        headers['content-type'] = 'application/json'
        headers['Authorization'] = f'Bearer {openai_api_key}'
        response = requests.get(
            f'{openai_base_url[:-3]}/dashboard/billing/subscription',
            headers=headers
        )
        return response

    # 获取使用信息
    @staticmethod
    async def get_usage(openai_api_key: str, openai_base_url: str):
        headers['user-agent'] = ua.random
        headers['content-type'] = 'application/json'
        headers['Authorization'] = f'Bearer {openai_api_key}'
        response = requests.get(
            f'{openai_base_url[:-3]}/dashboard/billing/usage',
            headers=headers
        )
        return response

    @staticmethod
    async def query_balance(openai_api_key: str, openai_base_url: str):
        headers['user-agent'] = ua.random
        headers['content-type'] = 'application/json'
        headers['Authorization'] = openai_api_key
        response = requests.post(
            f'{openai_base_url}/query/balance',
            headers=headers
        )
        if response.status_code == 200:

            return response.json()
        else:
            raise RuntimeError(response.text)
