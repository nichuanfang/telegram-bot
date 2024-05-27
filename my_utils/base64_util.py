import base64
import json


def base64_encode(json_dict: dict):
	"""base64编码

	Args:
		text (str): 待编码文本

	Returns:
		str: 编码后文本
	"""
	return base64.b64encode(json.dumps(
		json_dict).encode('utf-8')).decode('utf-8')


def base64_decode(text: str):
	"""base64解码

	Args:
		text (str): _description_

	Returns:
		_type_: _description_
	"""
	return json.loads(base64.b64decode(text).decode('utf-8'))