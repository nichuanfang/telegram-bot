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
        if stream:
            json_data = {
                "messages": new_messages,
                "stream": True,
                'model': context.user_data.get('current_model'),
                **openai_completion_options
            }
            async with SessionWithRetry(session, context).post(f'{self.openai_base_url}/chat/completions', json=json_data, headers=headers) as resp:
                sse_iter = SSE_DECODER.aiter_bytes(resp.content.iter_any())
                answer_parts = []
                async for sse in sse_iter:
                    answer_parts.append(sse.data)
                    answer = ''.join(answer_parts)
                    yield 'not_finished', answer
                yield 'finished', answer
        else:
            json_data = {
                "messages": new_messages,
                "stream": False,
                'model': context.user_data.get('current_model'),
                **openai_completion_options
            }
            completion = await self.chat.openai_client.chat.completions.create(**{
                "messages": new_messages,
                "stream": False,
                'model': context.user_data.get('current_model'),
                **openai_completion_options
            })
            answer = completion.choices[0].message.content
            yield answer
        await self.chat.append_messages(
            answer, context, *messages)
