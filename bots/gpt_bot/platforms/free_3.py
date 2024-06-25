# 免费的api平台 gpt-4
import json
import js2py
from fake_useragent import FakeUserAgent
import requests
from bots.gpt_bot.gpt_platform import Platform
from bots.gpt_bot.gpt_platform import gpt_platform
from telegram.ext import CallbackContext

ua = FakeUserAgent(browsers='chrome')

token_js = """
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
        payload = {"chas_style": "how-ai",
                   "chatHistory": json.dumps(new_messages)}
        agent = ua.random
        generateToken = js2py.eval_js(token_js)
        token = generateToken(agent)
        # api_key = js2py.eval_js(token_js.replace('agent', agent))
        headers = {
            "api-key": token,
            "User-Agent": agent,
        }
        response = requests.post("https://api.deepai.org/hacking_is_a_serious_crime",
                                 headers=headers, data=payload, stream=True)
        answer = ''
        for chunk in response.iter_content(chunk_size=None):
            response.raise_for_status()
            answer += chunk.decode()
            yield 'not_finished', answer
        yield 'finished', answer
        await self.chat.append_messages(
            answer, context, *messages)
