import asyncio
import os

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackContext, MessageHandler, filters
from tmdbv3api import TMDb, Search, Movie, TV

from my_utils import my_logging, bot_util

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
	await bot_util.send_typing(update)
	query = update.message.text
	try:
		responses = await asyncio.gather(bot_util.async_func(search.movies, query),
		                                 bot_util.async_func(search.tv_shows, query))
	except Exception as e:
		await update.message.reply_text(e)
		return
	movie_text = '*电影结果:*\n'
	movie_search = responses[0]
	tv_text = '*剧集结果:*\n'
	tv_search = responses[1]
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
		await update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True)
		await update.message.reply_text(tv_text, parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True)
	elif len(movie_search.results) > 0 and len(tv_search.results) == 0:
		await update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN_V2,
		                                reply_to_message_id=update.message.message_id, disable_web_page_preview=True)
	elif len(movie_search.results) == 0 and len(tv_search.results) > 0:
		await update.message.reply_text(tv_text, parse_mode=ParseMode.MARKDOWN_V2,
		                                reply_to_message_id=update.message.message_id, disable_web_page_preview=True)
	else:
		await update.message.reply_text('无任何结果!', reply_to_message_id=update.message.message_id)


async def movie_popular(update: Update, context: CallbackContext):
	"""
	推荐电影
	Args:
		update: 可以获取消息对象
		context:  可以获取机器人对象
	"""
	await bot_util.send_typing(update)
	try:
		res = await asyncio.gather(bot_util.async_func(movie.popular))
	except Exception as e:
		await update.message.reply_text(e)
		return
	
	movie_text = '*电影推荐:*\n'
	for movie_res in res[0].results:
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
	await update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN_V2,
	                                reply_to_message_id=update.message.message_id, disable_web_page_preview=True)


async def tv_popular(update: Update, context: CallbackContext):
	"""
	推荐剧集
	Args:
		update: 可以获取消息对象
		context:  可以获取机器人对象
	"""
	await bot_util.send_typing(update)
	try:
		res = await  asyncio.gather(bot_util.async_func(tv.popular))
	except Exception as e:
		await update.message.reply_text(e)
		return
	tv_text = '*剧集推荐:*\n'
	for tv_res in res[0].results:
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
	await update.message.reply_text(tv_text, parse_mode=ParseMode.MARKDOWN_V2,
	                                reply_to_message_id=update.message.message_id, disable_web_page_preview=True)


async def search_movie(update: Update, context: CallbackContext):
	"""获取TMDB电影信息

	Returns:
		_type_: _description_
	"""
	await bot_util.send_typing(update)
	message_text = update.message.text
	if message_text.strip() == '/movie_search':
		await update.message.reply_text('请输入电影名称!')
		return
	movie_text = '*电影结果:*\n'
	try:
		res = await asyncio.gather(bot_util.async_func(search.movies, message_text[14:]))
	except Exception as e:
		await update.message.reply_text(e)
		return
	movie_search = res[0]
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
		await update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN_V2,
		                                reply_to_message_id=update.message.message_id, disable_web_page_preview=True)
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
	await bot_util.send_typing(update)
	message_text = update.message.text
	if message_text.strip() == '/tv_search':
		await update.message.reply_text('请输入剧集名称!', reply_to_message_id=update.message.message_id)
		return
	tv_text = '*剧集结果:*\n'
	try:
		res = await asyncio.gather(bot_util.async_func(search.tv_shows, message_text[11:]))
	except Exception as e:
		await update.message.reply_text(e)
		return
	tv_search = res[0]
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
		await update.message.reply_text(tv_text, parse_mode=ParseMode.MARKDOWN_V2,
		                                reply_to_message_id=update.message.message_id, disable_web_page_preview=True)
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


def handlers():
	return [CommandHandler('movie_popular', movie_popular),
	        CommandHandler('tv_popular', tv_popular),
	        CommandHandler('movie_search', search_movie),
	        CommandHandler('tv_search', search_tv),
	        MessageHandler(filters.TEXT, default_search)]
