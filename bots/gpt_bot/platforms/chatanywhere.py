# Chatanywhere平台
from bots.gpt_bot.gpt_platform import Platform


# 注册为平台的方法 必须实现
def register():
	return PLATFORM_NAME, ChatAnywhere


PLATFORM_NAME = 'chatanywhere'


class ChatAnywhere(Platform):
	
	async def handle(self):
		# 业务处理方法
		pass
	
	async def query_balance(self):
		# 查询余额
		pass
	
	async def handle_audio_content(self):
		# 解析音频
		pass
	
	async def handle_image_content(self):
		# 解析图片
		pass
