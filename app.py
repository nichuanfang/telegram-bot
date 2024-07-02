import telegram
from my_utils import my_logging, validation_util
import dotenv
import aiocron
import traceback
import platform
import os
import multiprocessing
import asyncio
from telegram import Bot
from telegram.ext import ApplicationBuilder, ContextTypes, BaseRateLimiter

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

            if bot_directory == 'dogyun_bot':
                # 创建一个单独的进程来运行调度器
                p_scheduler = multiprocessing.Process(
                    target=run_scheduler, args=(token,))
                processes.append(p_scheduler)

            command_handlers = handlers()
            p_bot = multiprocessing.Process(target=start_bot, args=(
                bot_directory, token, command_handlers))
            processes.append(p_bot)

        except ImportError as e:
            logger.error(f"Failed to import bot {bot_directory}: {e}")
    return processes


async def add_scheduled_tasks(bot):
    from bots.dogyun_bot.scheduled_task import get_traffic_packet as gtp, lucky_draw_notice, balance_lack_notice

    @aiocron.crontab('0 0 7 * *')  # 每月7号
    async def get_traffic_packet():
        await gtp(bot)

    @aiocron.crontab('0 9 * * *')  # 每天9点
    async def lucky_draw_task():
        await lucky_draw_notice(bot)

    @aiocron.crontab('0 9 * * *')  # 每天9点
    async def balance_lack_task():
        await balance_lack_notice(bot)


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
        .read_timeout(15) \
        .write_timeout(15) \
        .connect_timeout(10) \
        .concurrent_updates(True) \
        .get_updates_read_timeout(120) \
        .get_updates_write_timeout(120) \
        .get_updates_connect_timeout(30) \
        .build()
    if command_handlers:
        application.add_handlers(command_handlers)
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
            listen='127.0.0.1',
            port=webhook_port,
            webhook_url=webhook_url,
            allowed_updates=['message', 'edited_message'],
            drop_pending_updates=True
        )


async def start_scheduler(token):
    bot = Bot(token=token)
    await add_scheduled_tasks(bot)
    logger.info("Scheduler started.")
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass


def run_scheduler(token):
    asyncio.run(start_scheduler(token))


if __name__ == '__main__':
    bot_directories = init()
    # Bootstrap!
    processes = bootstrap(logger, bot_directories)
    for p in processes:
        p.start()
    for p in processes:
        p.join()
