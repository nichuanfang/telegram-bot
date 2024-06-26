# 免费的api平台 gpt-4
import json
import platform
import ujson
import aiohttp
import js2py
from fake_useragent import FakeUserAgent
from bots.gpt_bot.gpt_platform import Platform
from bots.gpt_bot.gpt_platform import gpt_platform
from telegram.ext import CallbackContext

ua = FakeUserAgent(browsers='chrome')

DEEP_AI_TOKEN_JS = """
    function generateToken(agent) {
        var d, e, g, f, l, h, k, m, n, p, q, w, r, y, C, I, H, D, t, E, z, N, M, ca, O, P, S, T, J, R, Q, W, X, da, ia, Y, ea, Z, U, aa, fa, ha;
        p = Math.round(1E11 * Math.random()) + "";
        q = function() {
            for (var A = [], F = 0; 64 > F; )
                A[F] = 0 | 4294967296 * Math.sin(++F % Math.PI);
            return function(B) {
                var G, K, L, ba = [G = 1732584193, K = 4023233417, ~G, ~K], V = [], x = unescape(encodeURI(B)) + "\u0080", v = x.length;
                B = --v / 4 + 2 | 15;
                for (V[--B] = 8 * v; ~v; )
                    V[v >> 2] |= x.charCodeAt(v) << 8 * v--;
                for (F = x = 0; F < B; F += 16) {
                    for (v = ba; 64 > x; v = [L = v[3], G + ((L = v[0] + [G & K | ~G & L, L & G | ~L & K, G ^ K ^ L, K ^ (G | ~L)][v = x >> 4] + A[x] + ~~V[F | [x, 5 * x + 1, 3 * x + 5, 7 * x][v] & 15]) << (v = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21][4 * v + x++ % 4]) | L >>> -v), G, K])
                        G = v[1] | 0,
                        K = v[2];
                    for (x = 4; x; )
                        ba[--x] += v[x]
                }
                for (B = ""; 32 > x; )
                    B += (ba[x >> 3] >> 4 * (1 ^ x++) & 15).toString(16);
                return B.split("").reverse().join("")
            }
        }();

        return "tryit-" + p + "-" + q(agent + q(agent + q(agent + p + "x")));
    }
    """

HTTP_PROXY = 'http://127.0.0.1:10809' if platform.system().lower() == 'windows' else None


@gpt_platform
class Free_3(Platform):

    async def query_balance(self):
        """
        查询余额
        @return: 
        """
        return '已使用 $0.0 , 订阅总额 $0.0'

    async def completion(self, stream: bool, context: CallbackContext, *messages, **kwargs):
        new_messages, kwargs = self.chat.combine_messages(
            *messages, **kwargs)
        a: list = new_messages
        a.extend([
            {
                'role': 'user',
                'content': '请用中文回复我'
            },
            {
                'role': 'assistant',
                'content': '好的 语言已切换为中文'
            }])
        # 当前模型
        current_model = context.user_data['current_model']
        answer = ''
        if current_model == 'LLaMA':
            # 尝试deepinfra和deepai
            async for status, item in self.llama_complete(stream, new_messages):
                answer = item
                yield status, item
        elif current_model == 'gemini-1.5-flash-latest':
            # 谷歌的收费模型
            #     async for status, item in self.gemini_complete(stream, new_messages):
            #         answer = item
            #         yield status, item
            # await self.chat.append_messages(answer, context, *messages)
            pass
        await self.chat.append_messages(
            answer, context, *messages)

    # =========================================LLaMA===========================================

    async def llama_complete(self, stream: bool, new_messages: list):
        # 尝试 deepinfra 然后尝试deepai
        try:
            completion = self.deepai(stream, new_messages)
            async for status, item in completion:
                yield status, item
        except Exception as e:
            try:
                completion = self.deepinfra(stream, new_messages)
                async for status, item in completion:
                    yield status, item
            except:
                raise RuntimeError('LLaMA请求失败!')

    # =========================================LLaMA-DeepInfra===========================================
    async def deepinfra(self, stream: bool, new_messages: list):
        json_data = {
            "model": "meta-llama/Meta-Llama-3-70B-Instruct",
            "messages": new_messages,
            "stream": True
        }
        agent = ua.random
        headers = {
            "User-Agent": agent,
            "X-Deepinfra-Source": "web-page"
        }

        async with aiohttp.ClientSession() as session:
            answer = ''
            async with session.post("https://api.deepinfra.com/v1/openai/chat/completions", headers=headers, json=json_data, proxy=HTTP_PROXY) as response:
                response.raise_for_status()  # 检查请求是否成功
                flag = False
                async for item in response.content.iter_any():
                    try:
                        chunks = item.decode().splitlines()
                        for chunk in chunks:
                            if chunk:
                                if '[DONE]' in chunk:
                                    flag = True
                                    yield 'finished', answer
                                    break
                                else:
                                    delta = ujson.loads(chunk[6:])[
                                        'choices'][0]['delta']
                                    if delta:
                                        answer += delta['content']
                                        yield 'not_finished', answer
                    except:
                        continue
                if not flag:
                    yield 'finished', answer

    # =========================================LLaMA-Deepai===========================================

    async def deepai(self, stream: bool, new_messages: list):
        payload = {
            "chat_style": "chat",
            "chatHistory": json.dumps(new_messages)}
        agent = ua.random
        generateToken = js2py.eval_js(DEEP_AI_TOKEN_JS)
        token = generateToken(agent)
        headers = {
            "api-key": token,
            "User-Agent": agent,
        }
        async with aiohttp.ClientSession() as session:
            answer = ''
            async with session.post("https://api.deepai.org/hacking_is_a_serious_crime", headers=headers, data=payload, proxy=HTTP_PROXY) as response:
                response.raise_for_status()  # 检查请求是否成功
                async for item in response.content.iter_any():
                    try:
                        chunk = item.decode()
                        answer += chunk
                        yield 'not_finished', answer
                    except:
                        continue
                yield 'finished', answer
    # =========================================gemini-1.5-flash-latest===========================================

    async def gemini_complete(self, stream: bool, *new_messages):
        yield
