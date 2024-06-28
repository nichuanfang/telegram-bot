import os
import requests
from seleniumbase import Driver
import time

REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = os.getenv('REDIS_PORT')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
EMAIL = os.getenv('EMAIL')
PASSWORD: os.getenv('PASSWORD')

headers = {
    'Cookie': 'cf_clearance=XsimxDdgp4rQhdwG7lOwpD_CQTRZ3eAVMnNzKqzx3Qs-1719565316-1.0.1.1-ItHmGi5RSZSlr0rfw62VQfqk260a7YTWJCoovirUWScYKs.ESxTD2UhcjPyl14pEDT5uL2FrwaLKEn9Kx3jCOQ',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.138 Safari/537.36 AVG/112.0.21002.139'
}

json_data = {
    'email': 'f18326186224@gmail.com',
    'password': '0820nCf9270'
}

response = requests.post('https://chat.oaichat.cc/api/v1/auths/signin',
                         json=json_data, headers=headers)

pass

driver = Driver(
    browser="chrome",
    uc=True,
    headless2=True,
    incognito=True,
    agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.138 Safari/537.36 AVG/112.0.21002.139",
    do_not_track=True,
    undetectable=True
)

driver.get('https://chat.oaichat.cc')
time.sleep(20)
print(driver.get_cookies())
driver.quit()
