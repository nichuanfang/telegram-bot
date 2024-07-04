import asyncio
import traceback
from typing import List

from my_utils import my_logging
from telegram.ext import CallbackContext
from openai import AsyncOpenAI

# 生成摘要prompt提示
SUMMARY_PROMPT = '生成一个摘要.如果包含代码,总结代码片段的主要目的和功能，包括所使用的任何特定算法或技术'
# 生成摘要最大重试次数
SUMMARY_MAX_RETRIES = 2
# 日志模块
logger = my_logging.get_logger('chat')


class AKPool:
    """ 轮询获取api_key """

    def __init__(self, apikeys: list):
        self._pool = self._POOL(apikeys)

    def fetch_key(self):
        return next(self._pool)

    @classmethod
    def _POOL(cls, apikeys: list):
        while True:
            for x in apikeys:
                yield x


class MsgBase:
    role_name: str
    text: str

    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return self.text

    def __iter__(self):
        yield "role", self.role_name
        yield "content", self.text


system_msg = type("system_msg", (MsgBase,), {"role_name": "system"})
user_msg = type("user_msg", (MsgBase,), {"role_name": "user"})
assistant_msg = type("assistant_msg", (MsgBase,), {"role_name": "assistant"})


class Temque:
    """ 一个先进先出, 可设置最大容量, 可固定元素的队列 """

    def __init__(self, maxlen: int = None):  # type: ignore
        self.core: List[dict] = []
        self.maxlen = maxlen or float("inf")

    async def _trim(self, context: CallbackContext, is_platform_migrate: bool = False):
        is_claude: bool = context.user_data['current_model'].startswith(
            'claude-3')
        core = self.core
        if len(core) > self.maxlen:
            dc = len(core) - self.maxlen
            indexes = []
            for i, x in enumerate(core):
                indexes.append(i)
                if len(indexes) == dc:
                    # 如果是claude模型 还要保证此时的消息角色为user
                    if is_claude and x['obj']['role'] == 'user':
                        dc += 1
                    else:
                        break
            # [::-1]逆序输出
            for i in indexes[::-1]:
                core.pop(i)
        # 接下来进行历史消息处理流程
        # if not is_platform_migrate:
        #     # 平台迁移不处理历史消息了 只裁剪
        #     await self.process_history_message(core, context)

    async def add_many(self, context: CallbackContext = None, *objs):
        for x in objs:
            self.core.append({"obj": x})
        await self._trim(context)

    def __iter__(self):
        for x in self.core:
            yield x["obj"]

    def pin(self, *indexes):
        for i in indexes:
            self.core[i]["pin"] = True

    def unpin(self, *indexes):
        for i in indexes:
            self.core[i]["pin"] = False

    def copy(self):
        que = self.__class__(maxlen=self.maxlen)  # type: ignore
        que.core = self.core.copy()
        return que

    def deepcopy(self):
        ...  # 创建这个方法是为了以代码提示的方式提醒用户: copy 方法是浅拷贝

    def __add__(self, *obj: list):
        contents = []
        for message in self.core:
            contents.append(message['obj'])
        for item in obj:
            contents.append(item)
        return contents

    def drop_last(self):
        if len(self.core) > 0:
            # 移除最后一个元素
            self.core.pop()

    def clear(self):
        self.core = []

    async def process_history_message(self, core: List[dict], context: CallbackContext):
        for index, item in enumerate(core):
            if len(item['obj']['content']) < 1000:
                continue

            # todo  不进行摘要 改为压缩 (加快速度)

            # 每一个消息都需要重试
            asyncio.create_task(self.summary(
                context, index, item['obj']))

    async def summary(self, context: CallbackContext,  index: int, message: dict):
        """生成摘要

            Args:
                message (_type_): 历史消息
                index: 索引
                message: 需要摘要的消息
            """
        # 专门用于摘要历史消息的平台
        candidate_platform = context.user_data['candidate_platform']
        # 调用平台的接口生成摘要
        try:
            summary_content: str = await candidate_platform.summary(
                message, SUMMARY_PROMPT)
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f'生成摘要失败: \n{e}')
        # 更新生成的摘要信息
        message['content'] = summary_content
        try:
            self.core[index]['obj'] = message
        except:
            pass


async def coroutine_wrapper(normal_function, *args, **kwargs):
    return await asyncio.to_thread(normal_function, *args, **kwargs)


async def async_func(normal_function, *args, **kwargs):
    return await coroutine_wrapper(normal_function, *args, **kwargs)


class Chat:
    """
    [文档](https://lcctoor.github.io/arts/arts/openai2)

    获取api_key:
    * [获取链接1](https://platform.openai.com/account/api-keys)
    * [获取链接2](https://www.baidu.com/s?wd=%E8%8E%B7%E5%8F%96%20openai%20api_key)
    """

    recently_request_data: dict  # 最近一次请求所用的参数

    def __init__(self,
                 api_key: str | AKPool,
                 base_url: str = None,  # base_url 参数用于修改基础URL # type: ignore
                 timeout=None,
                 max_retries=None,
                 http_client=None,
                 max_message_count: int = 0,
                 **kwargs,
                 ):
        api_base = kwargs.pop('api_base', None)
        base_url = base_url or api_base
        if base_url:
            kwargs["base_url"] = base_url
        if timeout:
            kwargs["timeout"] = timeout
        if max_retries:
            kwargs["max_retries"] = max_retries
        if http_client:
            kwargs["http_client"] = http_client

        self.reset_api_key(api_key)
        self.openai_client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout,  # type: ignore
                                         max_retries=max_retries)  # type: ignore
        self._messages = Temque(maxlen=max_message_count)

    def set_max_message_count(self, max_count):
        # 设置最大历史消息数
        self._messages.maxlen = max_count

    def reset_api_key(self, api_key: str | AKPool):
        if isinstance(api_key, AKPool):
            self._akpool = api_key
        else:
            self._akpool = AKPool([api_key])

    def rollback(self, n=1):
        '''
        回滚对话
        '''
        self._messages.core[-2 * n:] = []
        for x in self._messages.core[-2:]:
            x = x["obj"]
            print(f"[{x['role']}]:{x['content']}")

    # def pin_messages(self, *indexes):
    #     '''
    #     锁定历史消息
    #     '''
    #     self._messages.pin(*indexes)

    # def unpin_messages(self, *indexes):
    #     '''
    #     解锁历史消息
    #     '''
    #     self._messages.unpin(*indexes)

    def fetch_messages(self):
        for item in self._messages.core:
            item['obj']

    def drop_last_message(self):
        self._messages.drop_last()

    async def recover_messages(self, context: CallbackContext):
        assert context.user_data
        clear_messages = context.user_data.get('clear_messages', None)
        if clear_messages:
            context.user_data['clear_messages'] = None
            new_queue = Temque(maxlen=self._messages.maxlen)
            await new_queue.add_many(
                context, *(clear_messages+list(self._messages)))
            self._messages = new_queue

    async def append_messages(self, answer, context, *messages):
        await self._messages.add_many(context, *messages, {"role": "assistant", "content": answer})

    def combine_messages(self, *messages, **openai_completion_options):
        return openai_completion_options.pop('messages', []) + (self._messages.__add__(*messages)), openai_completion_options

    def clear_messages(self, context: CallbackContext):
        """
        清空历史消息
        """
        user_data = context.user_data
        if len(self._messages.core) == 0:
            return
        user_data['clear_messages'] = list(self._messages)
        self._messages.clear()

    # def add_dialogs(self, *ms: dict | system_msg | user_msg | assistant_msg):
    #     '''
    #     添加历史对话
    #     '''
    #     messages = [dict(x) for x in ms]
    #     self._messages.add_many(*messages)

    def __getattr__(self, name):
        match name:  # 兼容旧代码
            case 'asy_request':
                return self.async_request
            # case 'forge':
            #     return self.add_dialogs
            # # case 'pin':
            #     return self.pin_messages
            # case 'unpin':
            #     return self.unpin_messages
            # case 'dump':
            #     return self._dump
            # case 'load':
            #     return self._load
        raise AttributeError(name)

    # def _dump(self, fpath: str):
    #     """ 存档 """
    #     messages = self.fetch_messages()
    #     jt = jsonDumps(messages, ensure_ascii=False)
    #     Path(fpath).write_text(jt, encoding="utf8")
    #     return True

    # def _load(self, fpath: str):
    #     """ 载入存档 """
    #     jt = Path(fpath).read_text(encoding="utf8")
    #     self._messages.add_many(*jsonLoads(jt))
    #     return True
