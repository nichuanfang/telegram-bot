# 定制化请求

import httpx
from fake_useragent import UserAgent

from my_utils.validation_util import validate

headers = {
	'content-type': 'application/json',
	'Accept-Encoding': 'gzip,compress,br,deflate',
	'Referer': 'https://servicewechat.com/wx759d07940a210802/6/page-frame.html',
	'Host': 'api.wsppx.cn',
	'Connection': 'keep-alive'
}
requires = validate('API_WSPPX_CN_TOKEN', 'API_WSPPX_CN_BASE_URL')
API_WSPPX_CN_TOKEN = requires[0]
API_WSPPX_CN_BASE_URL = requires[1]
headers['Authorization'] = API_WSPPX_CN_TOKEN

# 创建一个 UserAgent 实例
ua = UserAgent()


class WsppxHttpRequest:
	
	async def parse(self, url: str):
		"""
		分析url
		Returns:

		"""
		# 生成一个随机的 User-Agent
		headers['User-Agent'] = ua.random
		async with httpx.AsyncClient() as client:
			response = await client.post(
				f'{API_WSPPX_CN_BASE_URL}/qushuiyin/parse',
				headers=headers,
				json={
					'url': url
				}
			)
			return response.json()
