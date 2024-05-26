from telegram.ext import CommandHandler

from utils import my_logging

# 获取日志
logger = my_logging.get_logger('dogyun_bot')


async def main(updater, context):
	pass


def handlers():
	return [CommandHandler('main', main)]
