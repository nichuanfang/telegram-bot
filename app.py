from telegram import Update
from telegram._utils.types import ODVInput
from telegram.request import BaseRequest, RequestData
from typing import Optional, Tuple, Union
import aiohttp
import atexit
import datetime

from my_utils import my_logging, validation_util
import dotenv
import traceback
import platform
import os
import multiprocessing
from telegram.ext import ApplicationBuilder, ContextTypes
from pytz import timezone
from my_utils.global_var import GLOBAL_SESSION, atexit_handler
from telegram.request import BaseRequest

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


class AiohttpRequest(BaseRequest):
    def __init__(
        self,
        *,
        read_timeout: Optional[float] = None,
        write_timeout: Optional[float] = None,
        connect_timeout: Optional[float] = None,
        pool_timeout: Optional[float] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self._read_timeout = read_timeout
        self._write_timeout = write_timeout
        self._connect_timeout = connect_timeout
        self._pool_timeout = pool_timeout
        self.session = session or aiohttp.ClientSession()

    @property
    def read_timeout(self) -> Optional[float]:
        return self._read_timeout

    async def initialize(self) -> None:
        if self.session.closed:
            self.session = aiohttp.ClientSession()

    async def shutdown(self) -> None:
        await self.session.close()

    async def do_request(
        self,
        url: str,
        method: str,
        request_data: Optional[RequestData] = None,
        read_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
        write_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
        connect_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
        pool_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
    ) -> Tuple[int, bytes]:
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=connect_timeout if connect_timeout is not BaseRequest.DEFAULT_NONE else self._connect_timeout,
            sock_read=read_timeout if read_timeout is not BaseRequest.DEFAULT_NONE else self._read_timeout,
            sock_connect=write_timeout if write_timeout is not BaseRequest.DEFAULT_NONE else self._write_timeout,
        )

        async with self.session.request(
            method,
            url,
            data=request_data.json_parameters if request_data else None,
            timeout=timeout
        ) as response:
            status = response.status
            payload = await response.read()
            return status, payload


COMMON_REQUEST = AiohttpRequest(
    session=GLOBAL_SESSION,
    read_timeout=10,
    write_timeout=10,
    connect_timeout=10,
    pool_timeout=10,
)

# 支持的更新类型
ALLOWED_UPDATES = [Update.MESSAGE, Update.EDITED_MESSAGE,
                   Update.CALLBACK_QUERY, Update.INLINE_QUERY]


def start_bot(bot_name, token, command_handlers=None):

    if token is None:
        logger.error("请先设置BOT TOKEN!")
        return

    application = ApplicationBuilder() \
        .token(token) \
        .read_timeout(120) \
        .write_timeout(120) \
        .connect_timeout(30) \
        .concurrent_updates(True) \
        .get_updates_read_timeout(120) \
        .get_updates_write_timeout(120) \
        .get_updates_connect_timeout(30) \
        .build()

    if command_handlers:
        application.add_handlers(command_handlers)
    application.add_error_handler(error_handler)
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

    if platform.system().lower() == 'windows':
        logger.info(f"{bot_name} is started!!")
        application.run_polling(drop_pending_updates=True,
                                allowed_updates=ALLOWED_UPDATES)
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
            drop_pending_updates=True,
            allowed_updates=ALLOWED_UPDATES
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
