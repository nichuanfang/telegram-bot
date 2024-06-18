# 平台接口
import asyncio
import json
import os.path
from abc import ABCMeta
from typing import Union, List, Dict

import openai

from bots.gpt_bot.chat import Chat
import platform

from bots.gpt_bot.gpt_http_request import BotHttpRequest


def gpt_platform(cls):
	"""
	注册gpt转发平台的注解
	@return: 
	"""
	cls._is_gpt_platform = True
	return cls


# ABCMeta表明这是个抽象类
class Platform(metaclass=ABCMeta):
	# 分平台 是为了解决扩展性 以及 部分处理逻辑不同平台不兼容问题 比如 余额查询
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
			payment_url: str,
			max_message_count: int,
	):
		# 平台名称(英文)
		self.name = name
		# 平台名称(中文)
		self.name_zh = name_zh
		# 转发openai的base_url(国内专用)
		self.domestic_openai_base_url = domestic_openai_base_url
		# 转发openai的base_url(国外专用)
		self.foreign_openai_base_url = foreign_openai_base_url
		# 实际使用的base_url
		self.openai_base_url = domestic_openai_base_url if platform.system().lower() == 'windows' else foreign_openai_base_url
		# 转发openai的api_key
		self.openai_api_key = openai_api_key
		# 平台的首页
		self.index_url = index_url
		# 平台充值页面
		self.payment_url = payment_url
		# 最大历史消息容量
		self.max_message_count = max_message_count
		# 初始化参数
		chat_init_params = {
			"api_key": openai_api_key,
			"base_url": self.openai_base_url,
			"max_retries": openai.DEFAULT_MAX_RETRIES,
			"timeout": openai.DEFAULT_TIMEOUT,
			"max_message_count": max_message_count
		}
		
		self.chat = Chat(**chat_init_params)
	
	@classmethod
	def _platform_name(cls):
		"""
		获取类的模块名
		@return: 
		"""
		module = cls.__module__
		return os.path.basename(module.rsplit('.', 1)[1])
	
	async def async_request(self, content: Union[str, List, Dict] = None, **kwargs):
		"""
		非流式响应的请求逻辑
		@param content: 请求的内容
		@param kwargs: 其他字段
		"""
		messages_task = asyncio.create_task(self.prepare_messages(content))
		if kwargs.get('model') == "dall-e-3":
			messages = await messages_task
			# 需要生成图像
			yield await self.generate_image(messages)
		else:
			messages = await messages_task
			async for answer in self.completion(False, *messages, **kwargs):
				yield answer
	
	async def async_stream_request(self, content: Union[str, List, Dict] = None, **kwargs):
		"""
		流式响应的请求逻辑
		@param content:  请求内容
		@param is_free:  是否为免费key
		@param kwargs: 其他字段
		"""
		messages_task = asyncio.create_task(self.prepare_messages(content))
		if kwargs.get('model') == "dall-e-3":
			messages = await messages_task
			answer = await self.generate_image(messages)
			yield 'finished', answer
		else:
			messages = await messages_task
			async for status, answer in self.completion(True, *messages, **kwargs):
				yield status, answer
	
	async def completion(self, stream: bool, *messages, **kwargs):
		# 默认的提问方法
		new_messages, kwargs = self.chat.combine_messages(*messages, **kwargs)
		if stream:
			completion = await self.chat.openai_client.chat.completions.create(**{
				"messages": new_messages,
				"stream": True,
				**kwargs
			})
			answer: str = ""
			async for chunk_iter in completion:
				if chunk_iter.choices and (chunk := chunk_iter.choices[0].delta.content):
					answer += chunk
					yield 'not_finished', answer
			yield 'finished', answer
		else:
			completion = await self.chat.openai_client.chat.completions.create(**{
				"messages": new_messages,
				"stream": False,
				**kwargs
			})
			answer: str = completion.choices[0].message.content
			yield answer
		self.chat.append_messages(answer, *messages)
	
	async def prepare_messages(self, content: Union[str, List, Dict]) -> List[
		Dict[str, str]]:
		if isinstance(content, dict) and content.get('type') == "audio":
			return await self.audio_transcribe(content['audio_path'])
		# 如果类型是视频 这里需要对视频进行处理
		return [{"role": "user", "content": content}]
	
	async def generate_image(self, messages: List):
		# 生成图片
		generate_res = await self.chat.openai_client.images.generate(**{
			"prompt": messages[0]['content'],
			"model": 'dall-e-3',
			"style": "natural",
			"quality": "hd",
			"size": "1024x1024"
		})
		return generate_res.data[0].url
	
	async def audio_transcribe(self, ogg_path: str):
		# 音频转录
		try:
			# 创建转录
			with open(ogg_path, "rb") as audio_file:
				transcript = await self.chat.openai_client.audio.transcriptions.create(
					file=audio_file,
					model='whisper-1',
					language='zh',
					response_format="text"
				)
			return [{"role": "user", "content": transcript}]
		finally:
			if os.path.exists(ogg_path):
				os.remove(ogg_path)
	
	async def query_balance(self):
		# 查询余额
		responses = await asyncio.gather(BotHttpRequest.get_subscription(self.openai_api_key, self.openai_base_url),
		                                 BotHttpRequest.get_usage(self.openai_api_key, self.openai_base_url))
		subscription = responses[0]
		usage = responses[1]
		total = json.loads(subscription.text)['soft_limit_usd']
		used = json.loads(usage.text)['total_usage'] / 100
		return f'已使用 ${round(used, 2)} , 订阅总额 ${round(total, 2)}'
