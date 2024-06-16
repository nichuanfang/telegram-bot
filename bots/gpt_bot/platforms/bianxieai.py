# 便携AI平台
import asyncio
import json

from bots.gpt_bot.gpt_http_request import BotHttpRequest
from bots.gpt_bot.gpt_platform import Platform


# 注册为平台的方法 必须实现
def register():
	return PLATFORM_NAME, BianXieAI


PLATFORM_NAME = 'bianxieai'


class BianXieAI(Platform):
	
	async def handle(self):
		# 业务处理方法
		pass
	
	async def query_balance(self):
		# 查询余额
		request = BotHttpRequest()
		responses = await asyncio.gather(request.get_subscription(self.openai_api_key, self.openai_base_url),
		                                 request.get_usage(self.openai_api_key, self.openai_base_url))
		subscription = responses[0]
		usage = responses[1]
		total = json.loads(subscription.text)['soft_limit_usd']
		used = json.loads(usage.text)['total_usage'] / 100
		return f'已使用 ${round(used, 2)} , 订阅总额 ${round(total, 2)}'
	
	async def handle_audio_content(self):
		# 解析音频
		pass
	
	async def handle_image_content(self):
		# 解析图片
		pass
