# 平台接口
from abc import ABCMeta, abstractmethod


# ABCMeta表明这是个抽象类
class Platform(metaclass=ABCMeta):
	# 有不同的处理逻辑
	# 不同的余额查询方式
	# 可以直接在.env文件指定默认使用哪个平台 也可以通过机器人指令来动态切换平台
	# 新增充值指令 跳转到对应充值平台的页面
	# 免费key提供余额查询功能 查询当前可用次数
	# 该注解规定任何集成这个基类的必须实现该方法
	def __init__(
			self,
			name: str,
			name_zh: str,
			domestic_openai_base_url: str,
			foreign_openai_base_url: str,
			openai_api_key,
			index_url: str,
			payment_url: str
	):
		# 平台名称(英文)
		self.name = name
		# 平台名称(中文)
		self.name_zh = name_zh
		# 转发openai的base_url(国内专用)
		self.domestic_openai_base_url = domestic_openai_base_url
		# 转发openai的base_url(国外专用)
		self.foreign_openai_base_url = foreign_openai_base_url
		# 转发openai的api_key
		self.openai_api_key = openai_api_key
		# 平台的首页
		self.index_url = index_url
		# 平台充值页面
		self.payment_url = payment_url
	
	@abstractmethod
	def handle(self):
		# 业务处理方法
		pass
	
	@abstractmethod
	def query_balance(self):
		# 查询余额
		pass
