import os

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackContext, MessageHandler, filters
from tmdbv3api import TMDb, Search, Movie, TV

from my_utils import my_logging

# 获取日志
logger = my_logging.get_logger('tmdb_bot')

tmdb = TMDb()
tmdb.api_key = os.environ.get('TMDB_BOT_API_KEY')
tmdb.language = 'zh-CN'
search = Search()
movie = Movie()
tv = TV()


async def default_search(update: Update, context: CallbackContext):
	"""
	默认搜索
	Args:
		update: 可以获取消息对象
		context:  可以获取机器人对象
	"""
	query = update.message.text
	movie_text = '*电影结果:*\n'
	movie_search = search.movies(query)
	tv_text = '*剧集结果:*\n'
	tv_search = search.tv_shows(query)
	for movie_res in movie_search.results:
		try:
			if movie_res["release_date"] == None or movie_res["release_date"] == '':
				release_date = ''
			else:
				release_date = '(' + movie_res["release_date"].split("-")[0] + ')'
		except:
			release_date = ''
		movie_name = f'{movie_res.title} {release_date}'
		movie_tmdb_url = f'https://www.themoviedb.org/movie/{movie_res.id}?language=zh-CN'
		movie_text = movie_text + \
		             f'•  `{movie_name}`      [🔗]({movie_tmdb_url})\n'
	for tv_res in tv_search.results:
		try:
			if tv_res["first_air_date"] == None or tv_res["first_air_date"] == '':
				first_air_date = ''
			else:
				first_air_date = '(' + tv_res["first_air_date"].split("-")[0] + ')'
		except:
			first_air_date = ''
		tv_name = f'{tv_res.name} {first_air_date}'
		tv_tmdb_url = f'https://www.themoviedb.org/tv/{tv_res.id}?language=zh-CN'
		tv_text = tv_text + f'•  `{tv_name}`      [🔗]({tv_tmdb_url})\n'
	if len(movie_search.results) > 0 and len(tv_search.results) > 0:
		await update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN_V2)
		await update.message.reply_text(tv_text, parse_mode=ParseMode.MARKDOWN_V2)
	elif len(movie_search.results) > 0 and len(tv_search.results) == 0:
		await update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN_V2)
	elif len(movie_search.results) == 0 and len(tv_search.results) > 0:
		await update.message.reply_text(tv_text, parse_mode=ParseMode.MARKDOWN_V2)


async def movie_popular(update: Update, context: CallbackContext):
	"""
	推荐电影
	Args:
		update: 可以获取消息对象
		context:  可以获取机器人对象
	"""
	res = movie.popular()
	movie_text = '*电影推荐:*\n'
	for movie_res in res.results:
		try:
			if movie_res["release_date"] == None or movie_res["release_date"] == '':
				release_date = ''
			else:
				release_date = '(' + movie_res["release_date"].split("-")[0] + ')'
		except:
			release_date = ''
		movie_name = f'{movie_res.title} {release_date}'
		movie_tmdb_url = f'https://www.themoviedb.org/movie/{movie_res.id}?language=zh-CN'
		movie_text = movie_text + \
		             f'•  `{movie_name}`      [🔗]({movie_tmdb_url})\n'
	await update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN_V2)


async def tv_popular(update: Update, context: CallbackContext):
	"""
	推荐剧集
	Args:
		update: 可以获取消息对象
		context:  可以获取机器人对象
	"""
	res = tv.popular()
	tv_text = '*剧集推荐:*\n'
	for tv_res in res.results:
		try:
			if tv_res["first_air_date"] == None or tv_res["first_air_date"] == '':
				first_air_date = ''
			else:
				first_air_date = '(' + tv_res["first_air_date"].split("-")[0] + ')'
		except:
			first_air_date = ''
		tv_name = f'{tv_res.name} {first_air_date}'
		tv_tmdb_url = f'https://www.themoviedb.org/tv/{tv_res.id}?language=zh-CN'
		tv_text = tv_text + f'•  `{tv_name}`      [🔗]({tv_tmdb_url})\n'
	await update.message.reply_text(tv_text, parse_mode=ParseMode.MARKDOWN_V2)


async def search_movie(update: Update, context: CallbackContext):
	"""获取TMDB电影信息

	Returns:
		_type_: _description_
	"""
	message_text = update.message.text
	if message_text.strip() == '/movie_search':
		await update.message.reply_text('请输入电影名称!')
	movie_text = '*电影结果:*\n'
	movie_search = search.movies(message_text[14:])
	for movie_res in movie_search.results:
		try:
			if movie_res["release_date"] == None or movie_res["release_date"] == '':
				release_date = ''
			else:
				release_date = '(' + movie_res["release_date"].split("-")[0] + ')'
		except:
			release_date = ''
		movie_name = f'{movie_res.title} {release_date}'
		movie_tmdb_url = f'https://www.themoviedb.org/movie/{movie_res.id}?language=zh-CN'
		movie_text = movie_text + \
		             f'•  `{movie_name}`      [🔗]({movie_tmdb_url})\n'
	if len(movie_search.results) != 0:
		await update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN_V2)
	else:
		return None


async def search_movie_by_name(tmdb_name: str):
	"""获取TMDB电影信息

	Returns:
		_type_: _description_
	"""
	movie_search = search.movies(tmdb_name)
	if len(movie_search.results) != 0:
		# 将movie_search的结果转换为dict
		return movie_search.results
	else:
		return None


async def search_tv(update: Update, context: CallbackContext):
	"""获取TMDB剧集信息

	Returns:
		_type_: _description_
	"""
	message_text = update.message.text
	if message_text.strip() == '/tv_search':
		await update.message.reply_text('请输入剧集名称!')
	tv_text = '*剧集结果:*\n'
	tv_search = search.tv_shows(message_text[11:])
	for tv_res in tv_search.results:
		try:
			if tv_res["first_air_date"] == None or tv_res["first_air_date"] == '':
				first_air_date = ''
			else:
				first_air_date = '(' + tv_res["first_air_date"].split("-")[0] + ')'
		except:
			first_air_date = ''
		tv_name = f'{tv_res.name} {first_air_date}'
		tv_tmdb_url = f'https://www.themoviedb.org/tv/{tv_res.id}?language=zh-CN'
		tv_text = tv_text + f'•  `{tv_name}`      [🔗]({tv_tmdb_url})\n'
	if len(tv_search.results) != 0:
		await update.message.reply_text(tv_text, parse_mode=ParseMode.MARKDOWN_V2)
	else:
		return None


async def search_tv_by_name(tmdb_name: str):
	"""获取TMDB剧集信息

	Returns:
		_type_: _description_
	"""
	tv_search = search.tv_shows(tmdb_name)
	if len(tv_search.results) != 0:
		return tv_search.results
	else:
		return None


# @gpt_bot.message_handler(commands=['add_resource'])
# def add_resource(message):
# 	gpt_bot.reply_to(message, '请输入电影/剧集名称')
# 	gpt_bot.register_next_step_handler(message, add_resource_step)


# def add_resource_step(message):
# 	# 获取用户输入的电影/剧集名称
# 	tmdb_name = message.text.strip().replace(' ', '')
# 	if tmdb_name == '':
# 		gpt_bot.reply_to(message, '输入的电影/剧集名称不能为空!')
# 		gpt_bot.register_next_step_handler(message, add_resource_step)
# 		return
# 	elif tmdb_name.startswith('/'):
# 		return
# 	elif len(tmdb_name) > 100:
# 		gpt_bot.reply_to(message, '输入的电影/剧集名称不能超过100个字符!')
# 		gpt_bot.register_next_step_handler(message, add_resource_step)
# 		return
# 	# tmdb_name不能包含形如 (1995)这样的字符串
# 	elif tmdb_name.find('(') != -1 and tmdb_name.find(')') != -1:
# 		gpt_bot.reply_to(message, '输入的电影/剧集名称不合法!')
# 		gpt_bot.register_next_step_handler(message, add_resource_step)
# 		return
# 	movie_res = search_movie_by_name(tmdb_name)
# 	tv_res = search_tv_by_name(tmdb_name)
# 	if movie_res == None and tv_res == None:
# 		gpt_bot.reply_to(message, '未找到任何电影/剧集,请重新输入')
# 		gpt_bot.register_next_step_handler(message, add_resource)
# 	elif movie_res != None and tv_res == None:
# 		# 只存在电影 直接让用户选择目标电影
# 		markup_data = {}
# 		for index, movie_res_item in enumerate(movie_res):
# 			title = f'{index + 1}. {movie_res_item.title} ({movie_res_item.release_date.split("-")[0]})'
# 			markup_data[title] = {
# 				'callback_data': f'movie:{movie_res_item.id}'}
# 		movie_markup = quick_markup(markup_data, row_width=2)
# 		gpt_bot.reply_to(message, '请选择目标电影', reply_markup=movie_markup)
# 		gpt_bot.register_callback_query_handler(
# 			add_movie_callback, lambda query: query.data.startswith('movie:'))
#
# 	elif movie_res == None and tv_res != None:
# 		# 只存在剧集 直接让用户选择目标剧集
# 		markup_data = {}
# 		for index, tv_res_item in enumerate(tv_res):
# 			title = f'{index + 1}. {tv_res_item.name} ({tv_res_item.first_air_date.split("-")[0]})'
# 			markup_data[tv_res_item.name] = {
# 				'callback_data': f'tv:{tv_res_item.id}'}
# 		tv_markup = quick_markup(markup_data, row_width=2)
# 		gpt_bot.reply_to(message, '请选择目标剧集', reply_markup=tv_markup)
# 		gpt_bot.register_callback_query_handler(
# 			add_tv_callback, lambda query: query.data.startswith('tv:'))
# 	else:
# 		#  既存在电影又存在剧集 让用户选择电影/剧集
# 		markup = quick_markup({
# 			'电影': {'callback_data': f'choose_movie:{tmdb_name}'},
# 			'剧集': {'callback_data': f'choose_tv:{tmdb_name}'}
# 		}, row_width=2)
# 		gpt_bot.reply_to(message, '添加电影还是剧集?', reply_markup=markup)
# 		# 添加电影/剧集的回调函数 回调值为movie或tv
# 		gpt_bot.register_callback_query_handler(
# 			choose_movie_callback, lambda query: query.data.startswith('choose_movie:'))
# 		gpt_bot.register_callback_query_handler(
# 			choose_tv_callback, lambda query: query.data.startswith('choose_tv:'))


# def choose_movie_callback(query):
# 	tmdb_name = query.data.split(':')[1]
# 	# 根据tmdb_name查询电影
# 	movie_res = search_movie_by_name(tmdb_name)
# 	markup_data = {}
# 	# 让用户选择目标电影
# 	for index, movie_res_item in enumerate(movie_res):
# 		title = f'{index + 1}. {movie_res_item.title} ({movie_res_item.release_date.split("-")[0]})'
# 		markup_data[title] = {
# 			'callback_data': f'movie:{movie_res_item.id}'}
# 	movie_markup = quick_markup(markup_data, row_width=2)
# 	gpt_bot.send_message(query.message.chat.id, '请选择目标电影',
# 	                 reply_markup=movie_markup)
# 	gpt_bot.register_callback_query_handler(
# 		add_movie_callback, lambda query: query.data.startswith('movie:'))
#
#
# def choose_tv_callback(query):
# 	tmdb_name = query.data.split(':')[1]
# 	# 根据tmdb_name查询剧集
# 	tv_res = search_tv_by_name(tmdb_name)
# 	markup_data = {}
# 	# 让用户选择目标剧集
# 	for index, tv_res_item in enumerate(tv_res):
# 		title = f'{index + 1}. {tv_res_item.name} ({tv_res_item.first_air_date.split("-")[0]})'
# 		markup_data[title] = {
# 			'callback_data': f'tv:{tv_res_item.id}'}
# 	tv_markup = quick_markup(markup_data, row_width=2)
# 	gpt_bot.send_message(query.message.chat.id, '请选择目标剧集', reply_markup=tv_markup)
# 	gpt_bot.register_callback_query_handler(
# 		add_tv_callback, lambda query: query.data.startswith('tv:'))
#
#
# def add_movie_callback(query):
# 	movie_id = query.data.split(':')[1]
# 	# 查询电影详情
# 	movie_detail = movie.details(movie_id)
# 	# 要求输入分享链接
# 	gpt_bot.send_message(query.message.chat.id,
# 	                 f'请输入电影:`{movie_detail.title} ({movie_detail.release_date.split("-")[0]})`的分享链接',
# 	                 'MarkdownV2')
# 	gpt_bot.register_next_step_handler(query.message, add_movie_step, movie_id)
#
#
# def add_tv_callback(query):
# 	tv_id = query.data.split(':')[1]
# 	# 查询剧集详情
# 	tv_detail = tv.details(tv_id)
# 	# 要求输入分享链接
# 	gpt_bot.send_message(query.message.chat.id,
# 	                 f'请输入剧集:`{tv_detail.name} ({tv_detail.first_air_date.split("-")[0]})`的分享链接',
# 	                 'MarkdownV2')
# 	gpt_bot.register_next_step_handler(query.message, add_tv_step, tv_id)
#
#
# def add_movie_step(message, movie_id):
# 	# 如果分享链接以`/`开头 则说明是指令 直接退出
# 	if message.text.strip().startswith('/'):
# 		return
# 	# 获取用户输入的分享链接(支持批量) 通过正则表达式匹配url链接
# 	share_res: list[dict[str, str]] = regex_util.get_share_ids(
# 		message.html_text)
# 	# 获取电影详情
# 	movie_detail = movie.details(movie_id)
# 	gpt_bot.send_message(message.chat.id, '正在处理分享链接,请稍后...')
# 	# 处理分享链接
# 	share_links = alidrive_util.handle_share_res(
# 		f'{movie_detail.title} {movie_detail.release_date.split("-")[0]}', share_res)
# 	# 让用户选择分享链接对应的资源
# 	if len(share_links) == 0:
# 		gpt_bot.reply_to(message, '未找到任何有效的分享链接!请重新输入')
# 		gpt_bot.register_next_step_handler(message, add_movie_step, movie_id)
# 		return
# 	# 遍历share_links  返回一个列表
# 	response_text = '搜索结果：\n'
# 	for link in share_links:
# 		response_text = response_text + \
# 		                f'· <a href="{link["url"]}">{link["name"]}</a> \n'
# 	gpt_bot.send_message(message.chat.id, response_text, 'HTML')
#
#
# def add_tv_step(message, tv_id):
# 	# 如果分享链接以`/`开头 则说明是指令 直接退出
# 	if message.text.strip().startswith('/'):
# 		return
# 	# 获取用户输入的分享链接(支持批量) 通过正则表达式匹配url链接
# 	share_res: list[dict[str, str]] = regex_util.get_share_ids(
# 		message.html_text)
# 	# 获取电影详情
# 	tv_detail = tv.details(tv_id)
# 	gpt_bot.send_message(message.chat.id, '正在处理分享链接,请稍后...')
# 	# 处理分享链接
# 	share_links = alidrive_util.handle_share_res(
# 		f'{tv_detail.name} {tv_detail.first_air_date.split("-")[0]}', share_res)
# 	# 让用户选择分享链接对应的资源
# 	if len(share_links) == 0:
# 		gpt_bot.reply_to(message, '未找到任何有效的分享链接!请重新输入')
# 		gpt_bot.register_next_step_handler(message, add_tv_step, tv_id)
# 		return
# 	# 遍历share_links  返回一个列表
# 	response_text = '搜索结果：\n'
# 	for link in share_links:
# 		response_text = response_text + \
# 		                f'· <a href="{link["url"]}">{link["name"]}</a> \n'
# 	gpt_bot.send_message(message.chat.id, response_text, 'HTML')


# @gpt_bot.message_handler(content_types=['text'])
# def common(message):
#     raw_msg = message.text.strip().replace(' ', '')
#     if raw_msg and not raw_msg.startswith('/'):
#         message.text = '/movie_search '+raw_msg
#         movie_res = search_movie(message)
#         message.text = '/tv_search '+raw_msg
#         tv_res = search_tv(message)
#         if movie_res == None and tv_res == None:
#             gpt_bot.reply_to(message, '未找到任何电影剧集!')


def handlers():
	return [CommandHandler('movie_popular', movie_popular),
	        CommandHandler('tv_popular', tv_popular),
	        CommandHandler('movie_search', search_movie),
	        CommandHandler('tv_search', search_tv),
	        MessageHandler(filters.TEXT, default_search)]
