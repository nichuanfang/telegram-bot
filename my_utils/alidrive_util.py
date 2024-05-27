# 阿里云盘相关的工具模块
import base64
import json
import os
import re
import time

from aligo import Aligo

try:
	ALIGO_TOKEN = os.environ.get('ALIGO_TOKEN')
	aligo_config_str = base64.b64decode(
		ALIGO_TOKEN).decode(encoding='utf-8')
	aligo_config: dict = json.loads(aligo_config_str)
	refresh_token = aligo_config['refresh_token']
	device_id = aligo_config['device_id']
	x_device_id = aligo_config['x_device_id']
	aligo = Aligo(refresh_token=refresh_token, re_login=False)
	# 更新session的x-device-id
	aligo._session.headers.update({'x-device-id': x_device_id, 'x-signature': aligo._auth._X_SIGNATURE})
	aligo._auth.token.device_id = device_id
	aligo._auth.token.x_device_id = x_device_id
except Exception as e:
	# print('未配置环境变量ALIGO_TOKEN')
	# aligo = Aligo()
	raise Exception(f'请检查环境变量ALIGO_TOKEN是否正确: {e}')


def calculate_file_size(parent_file_id: str, share_token: str, max_recursion: int = 5):
	"""计算电影文件大小

	Args:
		parent_file_id (str): 父文件id
		share_token (str): 分享token
		max_recursion (int): 最大递归次数，默认为5

	Returns:
		float: 视频文件大小
	"""
	max_size = 0
	share_file = aligo.get_share_file(parent_file_id, share_token)
	if share_file.type == 'file':  # 如果是文件
		# 在这里根据文件类型判断是否是视频文件，可以使用相应的方法来获取文件大小
		if share_file.file_extension in ('mkv', 'mp4', 'avi', 'mov', 'wmv', 'flv', 'f4v', 'm4v', 'rmvb', 'rm', '3gp', 'dat', 'ts', 'mts', 'vob'):
			max_size = share_file.size
			max_recursion -= 1  # 处理视频文件时将递归次数减1
	elif max_recursion > 0:  # 如果是文件夹且递归次数大于0
		share_file_list = aligo.get_share_file_list(
			share_token, parent_file_id)
		for share_file in share_file_list:
			size = calculate_file_size(
				share_file.file_id, share_token, max_recursion)  # 递归调用时保持递归次数不变
			if size > max_size:
				max_size = size
	time.sleep(0.1)
	return max_size


def calculate_tv_file_size(parent_file_id: str, share_token: str):
	"""计算剧集文件大小

	Args:
		parent_file_id (str): 父文件id
		share_token (str): 分享token

	Returns:
		float: 视频文件大小
	"""
	share_file = aligo.get_share_file(parent_file_id, share_token)
	if share_file.type == 'file':  # 如果是文件
		# 在这里根据文件类型判断是否是视频文件，可以使用相应的方法来获取文件大小
		if share_file.file_extension in ('mkv', 'mp4', 'avi', 'mov', 'wmv', 'flv', 'f4v', 'm4v', 'rmvb', 'rm', '3gp', 'dat', 'ts', 'mts', 'vob'):
			return share_file.size
	else:  # 如果是文件夹
		share_file_list = aligo.get_share_file_list(
			share_token, parent_file_id)
		for share_file in share_file_list:
			size = calculate_tv_file_size(
				share_file.file_id, share_token)  # 传递正确的参数
			if size > 0:
				return size
	time.sleep(0.1)
	return 0


def extract_year(string: str) -> int:
	"""从字符串中提取年份

	Args:
		string (str): 输入字符串

	Returns:
		int: 提取到的年份，如果未找到或不在1900-2100范围内则返回0
	"""
	match = re.search(r'\b(\d{4})\b', string)
	if match:
		year = int(match.group(1))
		if 1900 <= year <= 2100:
			return year
	return 0


def calculate_similarity(str1: str, str2: str) -> float:
	"""计算两个字符串的匹配度

	Args:
		str1 (str): 第一个字符串
		str2 (str): 第二个字符串

	Returns:
		float: 匹配度，范围在0到1之间，值越大表示越相似
	"""
	# 提取非数字部分
	non_digit1 = re.sub(r'\s', '', re.sub(r'\d', '', str1))
	non_digit2 = re.sub(r'\s', '', re.sub(r'\d', '', str2))
	
	# 计算非数字部分的公共部分
	common_non_digit = set(non_digit1) & set(non_digit2)
	non_digit_similarity = len(common_non_digit) / len(non_digit1)
	
	if non_digit_similarity < 1:
		return 0.0
	
	# 提取数字部分（年份）
	digit1 = extract_year(str1)
	digit2 = extract_year(str2)
	
	# 检查数字部分是否为年份且相同
	if digit1 == digit2:
		digit_similarity = 1.0
	else:
		digit_similarity = 0.0
	
	# 综合计算相似度
	similarity = (non_digit_similarity + digit_similarity) / 2
	
	return similarity


def handle_share_res(name: str, share_res: list[dict[str, str]]):
	"""处理分享链接列表

	Args:
		name: 电影或剧集名称
		share_ids (list[str]): 分享链接列表
		type (str): 类型

	Returns:
		list[dict[str,str]]: 处理后的分享链接列表
	"""
	res = []
	for share_item in share_res:
		# 分享详情
		try:
			share_id = share_item['share_id']
			share_name = share_item['name']
			share_info = aligo.get_share_info(share_id)
		except:
			time.sleep(1)
			continue
		
		# 相似度匹配程度
		score = calculate_similarity(
			name, share_name)
		
		# 如果相似度小于0.25则跳过
		if score < 0.25:
			time.sleep(1)
			continue
		
		# 转为GB  保留两位小数
		# try:
		#     if type == 'movie':
		#         max_size = calculate_file_size(
		#             'root', share_token)
		#     elif type == 'tv':
		#         max_size = calculate_tv_file_size(
		#             'root', share_token)
		#     max_size = round(max_size / 1024 / 1024 / 1024, 2)
		# except:
		#     max_size = 0
		
		# 死链检测
		try:
			if share_info.file_count < 1 and len(share_info.file_infos) != 0 and share_info.file_infos[0].file_id != '':
				time.sleep(1)
				# 总文件数小于1
				continue
		except Exception as e:
			print(f'死链检测失败: {e}')
			time.sleep(1)
			continue
		
		res.append({
			'name': share_name,
			'url': f'https://www.aliyundrive.com/s/{share_id}',
			'score': score
		})
		time.sleep(1)
	# 根据score排序 从大到小
	res.sort(key=lambda x: x['score'], reverse=True)
	return res


if __name__ == '__main__':
	test_ids = ['BiTcxmfjeys', 'F3gwK1WQJs8']
	res = handle_share_res('阿凡达2', test_ids)
	pass