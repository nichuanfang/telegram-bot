# swt平台
from bots.gpt_bot.gpt_http_request import BotHttpRequest
from bots.gpt_bot.gpt_platform import Platform
from bots.gpt_bot.gpt_platform import gpt_platform


@gpt_platform
class Swt(Platform):

    async def query_balance(self):
        """
        查询余额
        @return: 
        """
        response = await BotHttpRequest.query_balance(self.openai_api_key, self.openai_base_url)
        return f'已使用 ${round(response["balanceUsed"], 2)} , 订阅总额 ${round(response["balanceTotal"], 2)}'
