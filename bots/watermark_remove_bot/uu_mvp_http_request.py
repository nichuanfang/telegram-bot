# 定制化请求

import httpx
from fake_useragent import UserAgent

from my_utils.validation_util import validate

headers = {
	'Accept-Encoding': 'gzip,compress,br,deflate',
	'Content-Type': 'application/json',
	'Connection': 'keep-alive',
	'Referer': 'https://servicewechat.com/wxd5fef542870462a7/3/page-frame.html',
	'Host': 'uu.yyymvp.com',
}
requires = validate('UU_MVP_BASE_URL')
UU_MVP_BASE_URL = requires[0]

# 创建一个 UserAgent 实例
ua = UserAgent()


class UuMvpHttpRequest:
	
	async def query(self, url: str):
		"""
		分析url
		Args:
			url: url

		Returns: 分析结果

		"""
		headers['User-Agent'] = ua.random
		async with httpx.AsyncClient() as client:
			response = await client.get(
				f'{UU_MVP_BASE_URL}/query',
				headers=headers,
				params={
					'url': url,
					'user_id': 5
				}
			)
			return response.json()