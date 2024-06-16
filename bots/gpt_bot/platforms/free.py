# 免费的api平台
from bots.gpt_bot.platform import Platform

PLATFORM_NAME = 'free'


class Free(Platform):
	
	def handle(self):
		# 业务处理方法
		pass
	
	def query_balance(self):
		# 查询余额
		pass
