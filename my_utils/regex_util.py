# 正则表达式相关的工具模块
import re


def is_valid_url(url):
	"""
	判断url合法性
	Args:
		url: url

	Returns: 是否合法

	"""
	regex = re.compile(
		r'^(?:http|ftp)s?://'  # http:// or https:// or ftp:// or ftps://
		r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
		r'localhost|'  # localhost...
		r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
		r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
		r'(?::\d+)?'  # optional port
		r'(?:/?|[/?]\S+)$', re.IGNORECASE)
	return re.match(regex, url) is not None


def get_share_ids(links: str):
	"""获取链接列表

	Args:
		links (str): 链接字符串

	Returns:
		list: 链接列表
		type (str): 链接类型
	"""
	splits = links.replace('\n\n', '\n').split('\n')
	res: list[dict[str, str]] = []
	# 正则表达式获取链接  https://www.aliyundrive.com/s/xxxxx
	pattern = re.compile(r'https://www.aliyundrive.com/s/(\w+)')
	for split in splits:
		if split.__contains__('<a href="https://www.aliyundrive.com/s/'):
			res.append({
				'name': split.rsplit('">', 1)[1].split('</a>', 1)[0],
				'share_id': pattern.findall(split)[0]
			})
		elif split.__contains__('·') and split.__contains__('(https://www.aliyundrive.com/s/'):
			# 例如  '·W 五月碧云天 1999 (https://www.aliyundrive.com/s/c5jeq18oCbh)'  name取 五月碧云天 1999  share_id取 c5jeq18oCbh
			res.append({
				'name': split.split('·', 1)[1].rsplit('(', 1)[0].strip(),
				'share_id': pattern.findall(split)[0]
			})
		elif split.__contains__('、') and split.__contains__('https://www.aliyundrive.com/s/'):
			# 去除 数字、
			res.append({
				'name': split.split('、', 1)[1].rsplit(':', 2)[0].strip(),
				'share_id': pattern.findall(split)[0]
			})
		elif split.__contains__('https://www.aliyundrive.com/s/'):
			# 剩余的 name取https://www.aliyundrive.com/s/前面的内容 share_id取正则表达式匹配到的内容
			res.append({
				'name': split.split('https://www.aliyundrive.com/s/')[0].strip(),
				'share_id': pattern.findall(split)[0]
			})
	
	return res


if __name__ == '__main__':
	res = get_share_ids(
		'1、功夫2004:https://www.aliyundrive.com/s/mLvZCu1tnXq;\n\n2、功夫2004:https://www.aliyundrive.com/s/LAFuZ7AjUu9;\n\n3、功夫2004:https://www.aliyundrive.com/s/F3gwK1WQJs8;\n\n4、功夫2004:https://www.aliyundrive.com/s/1VkiuN9H4cf;\n\n5、功夫2004:https://www.aliyundrive.com/s/6LC9Eg5Wjg6;\n\n6、功夫2004:https://www.aliyundrive.com/s/iwDdnf1RxJZ;\n\n7、功夫2004:https://www.aliyundrive.com/s/TENqmPqZsAh;\n\n8、(2004)功夫:https://www.aliyundrive.com/s/nd1CqaQa6gD;\n\n9、功夫足球2004:https://www.aliyundrive.com/s/dLXZUrdYRLQ;\n\n10、D功夫熊猫1国语:https://www.aliyundrive.com/s/nQxTaFfFVx4;\n\n·<a href="https://www.aliyundrive.com/s/yzoWMZkBByZ">G 功夫 (2004) 周星驰 豆瓣8.8</a>\n·<a href="https://www.aliyundrive.com/s/HL6jemwmxrK">功夫 (2004) 4K 60FPS 国粤双音轨，默认国语</a>\n·<a href="https://www.aliyundrive.com/s/Zc5LaEV5Yyz">4k120帧】《功夫》2004.周星驰经典高分喜剧电影，内嵌中文</a>\n·<a href="https://www.aliyundrive.com/s/Nm53CxtAVWd">G 功夫</a>\n·<a href="https://www.aliyundrive.com/s/nQfmk8s39Tf">G 功夫 Kung Fu</a>\n·<a href="https://www.aliyundrive.com/s/PhGDgsuwFsF">G 功夫瑜伽.Kung.Fu.Yoga.2017</a>\n·<a href="https://www.alipan.com/s/9nTFVmMxZbT">功夫[60帧率版本][高码版][国粤多音轨+中文字</a>\n·<a href="https://www.alipan.com/s/WdajMEFNpPy">功夫.2008.4K120帧.国语中英字幕</a>\n·<a href="https://www.aliyundrive.com/s/8K22AS6kNMc">功夫3D / Kung Fu Hustle</a>\n·<a href="https://www.aliyundrive.com/s/27qwzxic3fR">功夫熊猫：神龙骑士(2022) 3季全  1080p 内封简繁</a>\n·<a href="https://www.aliyundrive.com/s/FmmmG1GP5dc">周星驰《功夫》导评版，你可能没有看过的版本！未收录片段+花絮！</a>\n·<a href="https://www.aliyundrive.com/s/SKzgCjfR6x1">功夫熊猫：神龙骑士 (2022)</a>\n·<a href="https://www.aliyundrive.com/s/XcN31UoKbDf">文案功夫：成为金牌文案的6大核心能力</a>\n·<a href="https://www.aliyundrive.com/s/rBZPrCzxg8Z">《我在英国教功夫》 作者：马保国</a>\n·<a href="https://www.aliyundrive.com/s/JA9Qv2YrN6a">功夫熊猫：神龙骑士 Kung Fu Panda The Dragon Knight 1~2</a>\n·<a href="https://www.aliyundrive.com/s/Vj6AVkVrvXL">功夫熊猫 3部 1080p</a>\n·<a href="https://www.aliyundrive.com/s/NwMmczKxtjd">王牧笛.12招说话功夫</a>\n·<a href="https://www.aliyundrive.com/s/TN9WQAcucbw/folder/6156792a89ad3e04a6ea49c7876cb2fd0e832b79">功夫熊猫 123 国粤英</a>\n·<a href="https://www.aliyundrive.com/s/8dP6rAPbgcG/folder/60ea5ec7f5ea679d3cb14f32905dada73dcc2b9c">功夫熊猫 123 国粤英</a>\n·<a href="https://www.aliyundrive.com/s/mtFFDbM6wQg/folder/61150e5ec0da2c4de5bc42008578304a230a005e">功夫熊猫123+番外篇+tv版全集</a>')
	pass
