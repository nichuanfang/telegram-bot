# 免费的api平台 支持3.5-turbo
from bots.gpt_bot.gpt_platform import Platform
from bots.gpt_bot.gpt_platform import gpt_platform


@gpt_platform
class Free_1(Platform):

    # 1号池子比较特殊  需要配合base64密钥爬虫获取授权码 重写`completion`方法

    async def query_balance(self):
        """
        查询余额
        @return: 
        """
        return '已使用 $0.0 , 订阅总额 $0.0'
