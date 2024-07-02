import atexit
import datetime
from re import L

import httpx
from my_utils import my_logging, validation_util
import dotenv
import traceback
import platform
import os
import multiprocessing
from telegram.ext import ApplicationBuilder, ContextTypes, BaseRateLimiter
from pytz import timezone
from my_utils.global_var import atexit_handler
from httpx import AsyncClient, Limits

# 日志
logger = my_logging.get_logger('app')


def init():
    """ 初始化环境 """
    dotenv.load_dotenv(override=True)
    # 设置临时文件夹
    if not os.path.exists('temp'):
        os.mkdir('temp')
    # 获取 bots 目录下的所有子目录
    bot_directories = [d for d in os.listdir(
        'bots') if os.path.isdir(os.path.join('bots', d))]
    return bot_directories


def bootstrap(logger, bot_directories):
    """启动机器人核心方法"""
    processes = []
    # 动态加载每个机器人
    for bot_directory in bot_directories:
        try:
            if bot_directory == '__pycache__':
                continue
            bot_module = __import__(
                f'bots.{bot_directory}.bot', fromlist=['handlers'])
            handlers = getattr(bot_module, 'handlers')

            token = os.getenv(f'{bot_directory.upper()}_TOKEN')
            if token is None or len(token) == 0:
                logger.error(f'{bot_directory.upper()}_TOKEN未设置!')
            command_handlers = handlers()
            p_bot = multiprocessing.Process(target=start_bot, args=(
                bot_directory, token, command_handlers))
            processes.append(p_bot)
        except ImportError as e:
            logger.error(f"Failed to import bot {bot_directory}: {e}")
    return processes


async def error_handler(_: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles errors in the telegram-python-bot library.
    """
    logger.error(
        f"==================================================ERROR START==================================================================")
    logger.error(f'Exception while handling an update: {context.error}')
    traceback.print_exc()
    logger.error(
        f"==================================================ERROR END====================================================================")


def start_bot(bot_name, token, command_handlers=None):

    if token is None:
        logger.error("请先设置BOT TOKEN!")
        return
    application = ApplicationBuilder() \
        .token(token) \
        .write_timeout(15) \
        .connect_timeout(10) \
        .concurrent_updates(True) \
        .get_updates_read_timeout(60) \
        .get_updates_write_timeout(60) \
        .get_updates_connect_timeout(15) \
        .build()

    if command_handlers:
        application.add_handlers(command_handlers)
    # 特殊的机器人添加定时任务
    # 获取 JobQueue
    job_queue = application.job_queue
    # 设置时区为中国时区
    china_timezone = timezone('Asia/Shanghai')

    if bot_name == 'dogyun_bot':
        from bots.dogyun_bot.scheduled_task import get_traffic_packet, lucky_draw_notice, balance_lack_notice
        execute_time = datetime.time(
            hour=9, minute=0, second=0, tzinfo=china_timezone)
        # 获取每月流量包
        job_queue.run_monthly(get_traffic_packet, when=execute_time, day=7)
        # 抽奖活动通知
        job_queue.run_daily(lucky_draw_notice, time=execute_time)
        # 余额不足提醒
        job_queue.run_daily(balance_lack_notice, time=execute_time)
    application.add_error_handler(error_handler)

    if platform.system().lower() == 'windows':
        logger.info(f"{bot_name} is started!!")
        application.run_polling(drop_pending_updates=True)
    else:
        validate_res = validation_util.validate(
            f'{bot_name.upper()}_WEBHOOK_URL', f'{bot_name.upper()}_WEBHOOK_PORT')
        webhook_url = validate_res[0]
        webhook_port = validate_res[1]
        logger.info(
            f"{bot_name} is started at http://127.0.0.1:{webhook_port}!! remote webhook url: {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=webhook_port,
            webhook_url=webhook_url,
            url_path=f'webhook/{webhook_url.rsplit("/", 1)[-1]}',
            allowed_updates=['message', 'edited_message'],
            drop_pending_updates=True
        )


if __name__ == '__main__':
    atexit.register(atexit_handler)
    bot_directories = init()
    # Bootstrap!
    processes = bootstrap(logger, bot_directories)
    for p in processes:
        p.start()
    for p in processes:
        p.join()
