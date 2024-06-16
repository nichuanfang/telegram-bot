# 定制化请求

import httpx
from fake_useragent import UserAgent
from telegram.ext import CallbackContext

from bots.gpt_bot.gpt_platform import Platform

headers = {
	'accept': 'application/json',
	'accept-language': 'zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7,ja;q=0.6',
	'content-type': 'application/json',
	'origin': 'https://gpt.jaychou.site',
	'priority': 'u=1, i',
	'referer': 'https://gpt.jaychou.site/',
	'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
	'sec-ch-ua-mobile': '?0',
	'sec-ch-ua-platform': '"Windows"',
	'sec-fetch-dest': 'empty',
	'sec-fetch-mode': 'cors',
	'sec-fetch-site': 'cross-site'
}
# 创建一个 UserAgent 实例
ua = UserAgent()


class BotHttpRequest:
	
	# 获取订阅
	async def get_subscription(self, OPENAI_API_KEY: str, OPENAI_BASE_URL: str):
		# 生成一个随机的 User-Agent
		headers['user-agent'] = ua.random
		headers['authorization'] = f'Bearer {OPENAI_API_KEY}'
		async with httpx.AsyncClient() as client:
			response = await client.get(
				f'{OPENAI_BASE_URL[:-3]}/dashboard/billing/subscription',
				headers=headers
			)
		return response
	
	# 获取使用信息
	async def get_usage(self, OPENAI_API_KEY: str, OPENAI_BASE_URL: str):
		headers['user-agent'] = ua.random
		headers['authorization'] = f'Bearer {OPENAI_API_KEY}'
		async with httpx.AsyncClient() as client:
			response = await client.get(
				f'{OPENAI_BASE_URL[:-3]}/dashboard/billing/usage',
				headers=headers
			)
		return response
