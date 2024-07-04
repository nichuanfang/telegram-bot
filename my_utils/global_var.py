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

    def __init__(self, dns_map: Dict[str, Tuple[str, int]], default_dns: str, default_family=socket.AF_INET):
        self.dns_map = dns_map
        self.default_dns = default_dns
        self.default_family = default_family
        self.resolver = aiodns.DNSResolver(nameservers=[default_dns])

    def generate_result(self, host, answers, port, family):
        return [
            {
                'hostname': host,
                'host': answer.host,
                'port': port,
                'family': family,
                'proto': 0,
                'flags': 0,
            }
            for answer in answers
        ]

    def find_dns_config(self, host: str) -> Tuple[str, int]:
        """ 查找完整匹配或泛域名匹配的 DNS 配置 """
        parts = host.split('.')
        for i in range(len(parts)):
            domain = '.'.join(parts[i:])
            if domain in self.dns_map:
                return self.dns_map[domain]
        return self.default_dns, self.default_family

    async def _query(self, host: str, family: int, port: int) -> list:
        """ 进行 DNS 查询 """
        ipv4_res, ipv6_res = await asyncio.gather(
            self.resolver.query(host, 'A'),
            self.resolver.query(host, 'AAAA'),
            return_exceptions=True
        )
        if family == socket.AF_INET:
            if ipv4_res and not isinstance(ipv4_res, BaseException):
                return self.generate_result(host, ipv4_res, port, socket.AF_INET)
            elif ipv6_res and not isinstance(ipv6_res, BaseException):
                return self.generate_result(host, ipv6_res, port, socket.AF_INET6)
            else:
                return [{
                    'hostname': host,
                    'host': None,
                    'port': port,
                    'family': family,
                    'proto': 0,
                    'flags': 0,
                }]
        else:
            if ipv6_res and not isinstance(ipv6_res, BaseException):
                return self.generate_result(host, ipv6_res, port, socket.AF_INET6)
            elif ipv4_res and not isinstance(ipv4_res, BaseException):
                return self.generate_result(host, ipv4_res, port, socket.AF_INET)
            else:
                return [{
                    'hostname': host,
                    'host': None,
                    'port': port,
                    'family': family,
                    'proto': 0,
                    'flags': 0,
                }]

    async def resolve(self, host: str, port=0, family=socket.AF_UNSPEC) -> list:
        """ 解析给定主机名的地址 """
        dns, priority_family = self.find_dns_config(host)
        family = priority_family if family == socket.AF_UNSPEC else family
        self.resolver.nameservers = [dns]
        return await self._query(host, family, port)

    async def close(self):
        """ 关闭解析器 """
        pass


dns_map = {
    # 'example.com': ('223.5.5.5', socket.AF_INET)
}
# 配合smartdns查询
default_dns = '127.0.0.1'
# 优先返回ipv4记录
default_family = socket.AF_INET
# 创建自定义解析器实例
custom_resolver = CustomResolver(dns_map, default_dns, default_family)

# 全局会话
GLOBAL_SESSION = aiohttp.ClientSession(
    trust_env=True,  # 是否使用代理
    raise_for_status=True,  # 自动抛异常
    timeout=aiohttp.ClientTimeout(total=300),
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
