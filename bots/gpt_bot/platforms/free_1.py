# 免费的api平台 支持3.5-turbo
import aiohttp
from bots.gpt_bot.core.session import SessionWithRetry
from bots.gpt_bot.core.streaming import SSE_DECODER
from bots.gpt_bot.gpt_platform import Platform
from bots.gpt_bot.gpt_platform import gpt_platform
from my_utils.bot_util import ua


@gpt_platform
class Free_1(Platform):

    async def query_balance(self):
        """
        查询余额
        @return: 
        """
        return '已使用 $0.0 , 订阅总额 $0.0'

    async def completion(self, stream: bool,  context, session: aiohttp.ClientSession, *messages):
        # 默认的提问方法
        openai_completion_options = context.user_data['current_mask']['openai_completion_options']
        new_messages, openai_completion_options = self.chat.combine_messages(
            *messages, **openai_completion_options)
        answer = ''
        headers = {
            'origin': self.foreign_openai_base_url,
            'user-agent': ua.random,
            'authorization': self.openai_api_key,
        }
        json_data = {
            "messages": new_messages,
            "stream": stream,
            'model': context.user_data.get('current_model'),
            **openai_completion_options
        }
        if stream:
            async for status, answer in SessionWithRetry(session, context).post(f'{self.foreign_openai_base_url}/chat/completions', headers=headers, json=json_data, stream=True):
                yield status, answer
        else:
            async for answer in SessionWithRetry(session, context).post(f'{self.foreign_openai_base_url}/chat/completions', headers=headers, json=json_data):
                yield answer
        await self.chat.append_messages(
            answer, context, *messages)
