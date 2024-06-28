from seleniumbase import Driver
import time

driver = Driver(
    browser="chrome",
    uc=True,
    headless2=True,
    incognito=True,
    # agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.138 Safari/537.36 AVG/112.0.21002.139",
    do_not_track=True,
    undetectable=True
)

driver.get('https://chat.oaichat.cc')
time.sleep(20)
print(driver.get_cookies())
driver.quit()
