from json import dumps as jsonDumps
from json import loads as jsonLoads
from pathlib import Path
from typing import List

from openai import AsyncOpenAI
from telegram.ext import CallbackContext


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

    def _trim(self):
        core = self.core
        if len(core) > self.maxlen:
            dc = len(core) - self.maxlen
            indexes = []
            for i, x in enumerate(core):
                # if not x["pin"]:
                indexes.append(i)
                if len(indexes) == dc:
                    break
            for i in indexes[::-1]:
                core.pop(i)

    def add_many(self, *objs):
        for x in objs:
            self.core.append({"obj": x})
        self._trim()

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

    def __add__(self, obj: 'list|Temque'):
        que = self.copy()
        if isinstance(obj, self.__class__):
            que.core += obj.core
            que._trim()
        else:
            que.add_many(*obj)
        return que

    def drop_last(self):
        if len(self.core) > 0:
            # 移除最后一个元素
            self.core.pop()

    def clear(self):
        """清空队列中的所有元素"""
        self.core = []


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

    def pin_messages(self, *indexes):
        '''
        锁定历史消息
        '''
        self._messages.pin(*indexes)

    def unpin_messages(self, *indexes):
        '''
        解锁历史消息
        '''
        self._messages.unpin(*indexes)

    def fetch_messages(self):
        return list(self._messages)

    def drop_last_message(self):
        self._messages.drop_last()

    def recover_messages(self, context: CallbackContext):
        assert context.user_data
        clear_messages = context.user_data.get('clear_messages', None)
        if clear_messages:
            context.user_data['clear_messages'] = None
            new_queue = Temque(maxlen=5)
            new_queue.add_many(*clear_messages)
            new_queue.add_many(*list(self._messages))
            self._messages = new_queue

    def append_messages(self, answer, *messages):
        self._messages.add_many(
            *messages, {"role": "assistant", "content": answer})

    def combine_messages(self, *messages, **kwargs):
        if kwargs['model'].startswith('claude-3'):
            flag = len(
                self._messages.core) == self._messages.maxlen and self._messages.core[0]['obj']['role'] == 'user'
            if flag:
                # 移除第一个元素
                self._messages.drop_last()
        return kwargs.pop('messages', []) + list(self._messages + messages), kwargs

    def clear_messages(self, context: CallbackContext):
        """
        清空历史消息
        """
        user_data = context.user_data
        if len(self._messages.core) == 0:
            return
        user_data['clear_messages'] = list(self._messages)
        self._messages.clear()

    def add_dialogs(self, *ms: dict | system_msg | user_msg | assistant_msg):
        '''
        添加历史对话
        '''
        messages = [dict(x) for x in ms]
        self._messages.add_many(*messages)

    def __getattr__(self, name):
        match name:  # 兼容旧代码
            case 'asy_request':
                return self.async_request
            case 'forge':
                return self.add_dialogs
            case 'pin':
                return self.pin_messages
            case 'unpin':
                return self.unpin_messages
            case 'dump':
                return self._dump
            case 'load':
                return self._load
        raise AttributeError(name)

    def _dump(self, fpath: str):
        """ 存档 """
        messages = self.fetch_messages()
        jt = jsonDumps(messages, ensure_ascii=False)
        Path(fpath).write_text(jt, encoding="utf8")
        return True

    def _load(self, fpath: str):
        """ 载入存档 """
        jt = Path(fpath).read_text(encoding="utf8")
        self._messages.add_many(*jsonLoads(jt))
        return True
