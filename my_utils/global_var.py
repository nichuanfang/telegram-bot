# 创建全局 aiohttp.ClientSession 对象
import sys
from typing import Dict, Tuple
import asyncio
import socket
import aiohttp
from redis import ConnectionPool
import aiodns
from my_utils import redis_util

# 修复windows下aiodns报错
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy())


class CustomResolver(aiohttp.abc.AbstractResolver):
    """ 自定义dns解析器 """

    def __init__(self, used_dns: str):
        self.resolver = aiodns.DNSResolver(nameservers=[used_dns])

    async def _query(self, host: str, family: int, port: int) -> list:
        """ 进行 DNS 查询 """

        # 只查询A记录
        result = await self.resolver.query(host, 'A')
        return [
            {
                'hostname': host,
                'host': answer.host,
                'port': port,
                'family': family,
                'proto': 0,
                'flags': 0,
            }
            for answer in result
        ]

    async def resolve(self, host: str, port=0, family=socket.AF_UNSPEC) -> list:
        """ 解析给定主机名的地址 """
        return await self._query(host, family, port)

    async def close(self):
        """ 关闭解析器 """
        pass


# 创建自定义解析器实例
custom_resolver = CustomResolver('127.0.0.1')

# 全局会话
GLOBAL_SESSION = aiohttp.ClientSession(
    trust_env=True,  # 是否使用代理
    raise_for_status=True,  # 自动抛异常
    timeout=aiohttp.ClientTimeout(total=300),  # 总超时
    connector_owner=True,  # 拥有连接池控制权
    connector=aiohttp.TCPConnector(
        limit=100,  # 最大连接数
        limit_per_host=10,  # 每个主机的最大连接数
        resolver=custom_resolver,  # 配置dns解析器
        use_dns_cache=True,  # 是否使用dns缓存
        ttl_dns_cache=3600,  # dns缓存时间
        keepalive_timeout=3600  # 空闲连接存活时间
    )
)

# Redis连接池用于存储每日访问计数和过期时间
REDIS_POOL: ConnectionPool = redis_util.create_redis_pool()


async def close_session():
    """ 关闭连接 """
    await GLOBAL_SESSION.close()
    redis_util.close_redis_pool(REDIS_POOL)


def atexit_handler():
    """ 关闭处理器 """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(close_session())
