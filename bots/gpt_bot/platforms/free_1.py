# 免费的api平台
from bots.gpt_bot.gpt_http_request import BotHttpRequest
from bots.gpt_bot.gpt_platform import Platform
from bots.gpt_bot.gpt_platform import gpt_platform


@gpt_platform
class Free_1(Platform):
	
	async def query_balance(self):
		"""
		查询余额
		@return: 
		"""
		return '已使用 $0.0 , 订阅总额 $0.0'
