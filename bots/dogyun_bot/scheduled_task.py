""" 定时任务 """
import re
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup
from telegram import Bot

from my_utils import my_logging
from my_utils.validation_util import validate
# 获取日志
logger = my_logging.get_logger('dogyun_bot')

values = validate('DOGYUN_BOT_SERVER_ID', 'DOGYUN_BOT_CSRF_TOKEN',
                  'DOGYUN_BOT_COOKIE', 'DOGYUN_BOT_CHAT_ID')

DOGYUN_BOT_SERVER_ID = values[0]
DOGYUN_BOT_CSRF_TOKEN = values[1]
DOGYUN_BOT_COOKIE = values[2]
DOGYUN_BOT_CHAT_ID = values[3]


# 每月7号
async def get_traffic_packet(bot: Bot):

    url = f'https://cvm.dogyun.com/traffic/package/level'
    headers = {
        'X-Csrf-Token': DOGYUN_BOT_CSRF_TOKEN,
        'Origin': 'https://cvm.dogyun.com',
        'Referer': 'https://cvm.dogyun.com/traffic/package/list',
        'Cookie': DOGYUN_BOT_COOKIE
    }

    try:
        # 发送post请求
        response = requests.post(url, headers=headers, verify=True)
        if response.url == 'https://account.dogyun.com/login':
            # tg通知dogyun cookie已过期
            await bot.send_message(DOGYUN_BOT_CHAT_ID, 'dogyun cookie已过期,请更新cookie!')
            return
        data = response.json()
    except Exception as e:
        logger.error(e)
        return
    # 获取领取结果
    try:
        result = data['message']
    except Exception as e:
        await bot.send_message(DOGYUN_BOT_CHAT_ID, f'领取失败: {e}')
        return
    # 获取当前时间
    now = datetime.now()
    # 获取当前日期
    today = date.today()
    # 获取当前时间
    current_time = now.strftime("%H:%M:%S")
    # 获取当前日期
    current_date = today.strftime("%Y-%m-%d")
    # 记录日志
    logger.info(f'{current_date} {current_time} {result}')
    # 发送通知
    await bot.send_message(DOGYUN_BOT_CHAT_ID, f'等级奖励通用流量包: {result}')


async def lucky_draw_notice(bot: Bot):
    """抽奖活动通知
    """
    url = f'https://console.dogyun.com/turntable'
    headers = {
        'Cookie': DOGYUN_BOT_COOKIE,
        'Referer': 'https://member.dogyun.com/',
        'Origin': 'https://console.dogyun.com',
        'X-Csrf-Token': DOGYUN_BOT_CSRF_TOKEN
    }
    try:
        # 发起get请求
        response = requests.get(url, headers=headers, verify=True)
        if response.url == 'https://account.dogyun.com/login':
            # tg通知dogyun cookie已过期
            await bot.send_message(DOGYUN_BOT_CHAT_ID, 'dogyun cookie已过期,请更新cookie!')
            return
    except Exception as e:
        logger.error(e)
        return
    soup = BeautifulSoup(response.text, 'lxml')
    try:
        result = soup.find("strong")
        if result is not None:
            await bot.send_message(DOGYUN_BOT_CHAT_ID, f'抽奖活动通知: {soup.find("strong").text}')
            logger.info(f'抽奖活动通知: {soup.find("strong").text}')
        else:
            pass
    except:
        # '暂无抽奖活动'
        # await bot.send_message(DOGYUN_BOT_CHAT_ID,f'暂无抽奖活动')
        pass


# 余额不足提醒
async def balance_lack_notice(bot: Bot):
    """余额不足提醒
    """
    url = f'https://console.dogyun.com'
    headers = {
        'Cookie': DOGYUN_BOT_COOKIE,
        'Referer': 'https://member.dogyun.com/',
        'Origin': 'https://console.dogyun.com',
        'X-Csrf-Token': DOGYUN_BOT_CSRF_TOKEN
    }
    try:
        # 发起get请求
        response = requests.get(url, headers=headers, verify=True)
        if response.url == 'https://account.dogyun.com/login':
            # tg通知dogyun cookie已过期
            await bot.send_message(DOGYUN_BOT_CHAT_ID, 'dogyun cookie已过期,请更新cookie!')
            return
    except Exception as e:
        logger.error(e)
        return
    soup = BeautifulSoup(response.text, 'lxml')
    try:
        result = soup.find('span', class_='h5 font-weight-normal').text
        # 根据正则表达式提取数字
        balance = re.findall(r"\d+\.?\d*", result)[0]
        if float(balance) < 10:
            await bot.send_message(DOGYUN_BOT_CHAT_ID, f'余额不足提醒: {balance}元')
            logger.info(f'余额不足提醒: {balance}元')
    except:
        pass
