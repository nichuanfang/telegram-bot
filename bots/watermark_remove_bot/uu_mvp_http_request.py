# 定制化请求

from fake_useragent import FakeUserAgent
from my_utils.global_var import GLOBAL_SESSION as session
from my_utils.validation_util import validate


requires = validate('UU_MVP_BASE_URL')
UU_MVP_BASE_URL = requires[0]

# 创建一个 UserAgent 实例
ua = FakeUserAgent(browsers='chrome', os='windows', platforms='pc')


class UuMvpHttpRequest:

    async def query(self, url: str):
        """
        分析url
        Args:
                url: url

        Returns: 分析结果

        """
        headers = {
            'User-Agent': ua.random
        }
        async with session.get(
            f'{UU_MVP_BASE_URL}/query',
            headers=headers,
            params={
                'url': url,
                'user_id': 5
            }
        ) as response:
            return await response.json()
