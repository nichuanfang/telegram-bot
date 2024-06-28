import os
import requests
from fake_useragent import FakeUserAgent
from seleniumbase import Driver
import time
import json

ua = FakeUserAgent(browsers='chrome')

REDIS_HOST = os.getenv('REDIS_HOST', '103.30.77.144')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '123456')
EMAIL = os.getenv('EMAIL', 'f18326186224@gmail.com')
PASSWORD = os.getenv('PASSWORD', '0820nCf9270')


def acquire_cf_cookie(agent: str):
    """ 根据ua获取cf_cookie """
    driver = Driver(
        browser="chrome",
        uc=True,
        headless2=True,
        incognito=True,
        agent=agent,
        do_not_track=True,
        undetectable=True
    )
    driver.get('https://chat.oaichat.cc')
    cookies = driver.get_cookies()
    time.sleep(20)
    driver.quit()
    if cookies:
        return f'{cookies[0]["name"]}={cookies[0]["value"]}'
    else:
        raise Exception('获取cookie失败!')


def signin(agent: str, cf_cookie: str, email: str, password: str):
    """ 获取授权信息 """
    headers = {
        'Cookie': cf_cookie,
        'Content-Type': 'application/json',
        'User-Agent': agent
    }
    json_data = {
        'email': email,
        'password': password
    }
    response = requests.post('https://chat.oaichat.cc/api/v1/auths/signin',
                             json=json_data, headers=headers)
    # 获取登录信息
    if response.status_code == 200:
        return json.loads(response.text)
    raise Exception('获取登录信息失败!')


def assembe_and_store():
    """ 封装open_api_key并存储到redis中 """
    pass


if __name__ == '__main__':
    agent = ua.random
    cf_cookie = acquire_cf_cookie(agent)
    print(cf_cookie)
    res = signin(agent, cf_cookie, EMAIL, PASSWORD)
    print(res)
