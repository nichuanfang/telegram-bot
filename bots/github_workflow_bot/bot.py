import asyncio

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from my_utils import my_logging, bot_util
from my_utils.bot_util import auth
from my_utils.github_util import trigger_github_workflow
from my_utils.global_var import GLOBAL_SESSION as session

# 获取日志
logger = my_logging.get_logger('github_workflow_bot')


@auth
async def scrape_metadata(update: Update, context: CallbackContext):
    """刮削影视元信息

    Returns:
            _type_: _description_
    """
    await bot_util.send_typing(update)
    try:
        await trigger_github_workflow(session, 'movie-tvshow-spider',
                                      'crawl movies and shows')
    except Exception as e:
        await update.message.reply_text(e, reply_to_message_id=update.message.message_id)
        return
    logger.info('Scraped!')
    await update.message.reply_text(
        '已触发工作流: 刮削影视元信息,查看刮削日志: https://github.com/nichuanfang/movie-tvshow-spider/actions',
        reply_to_message_id=update.message.message_id)


def handlers():
    return [CommandHandler('scrape_metadata', scrape_metadata)]
