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
    """自定义 DNS 解析器"""

    def __init__(self, dns_map: Dict[str, Tuple[str, int]], default_dns: str, default_family=socket.AF_INET6):
        self.dns_map = dns_map
        self.default_dns = default_dns
        self.default_family = default_family
        self.resolver = aiodns.DNSResolver(
            nameservers=[self.default_dns])  # 设置默认的 DNS 服务器

    def find_dns_config(self, host: str):
        # 查找完整匹配或泛域名匹配的 DNS 配置
        parts = host.split('.')
        for i in range(len(parts)):
            domain = '.'.join(parts[i:])
            if domain in self.dns_map:
                return self.dns_map[domain]
        return self.default_dns, self.default_family

    async def _query(self, host, record_type, family, port):
        try:
            answers = await self.resolver.query(host, record_type, family=family)
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
        except aiodns.error.DNSError:
            return []

    async def resolve(self, host, port=0, family=socket.AF_UNSPEC):
        # 获取对应域名的 DNS 配置和优先级
        dns, priority_family = self.find_dns_config(host)

        # 如果没有指定优先级，则使用请求时的 family，默认为 IPv6
        family = priority_family if family == socket.AF_UNSPEC else family

        # 更新 resolver 的 nameservers，确保使用正确的 DNS 服务器
        self.resolver.nameservers = [dns]

        # 尝试按照优先级进行查询
        record_types = [
            'AAAA', 'A'] if family == socket.AF_INET6 else ['A', 'AAAA']
        results_ipv4 = []
        results_ipv6 = []

        # 并行查询 IPv4 和 IPv6 结果
        tasks = []
        for record_type, fam in zip(record_types, [socket.AF_INET, socket.AF_INET6]):
            tasks.append(self._query(host, record_type, fam, port))

        # 并行执行任务
        results = await asyncio.gather(*tasks)

        # 整理结果，按照优先级返回
        for result in results:
            if result:
                if result[0]['family'] == socket.AF_INET:
                    results_ipv4.extend(result)
                elif result[0]['family'] == socket.AF_INET6:
                    results_ipv6.extend(result)

        # 如果两种结果都为空，则返回空列表
        if not results_ipv4 and not results_ipv6:
            return []

        # 按照优先级返回结果
        if family == socket.AF_INET6:
            return results_ipv6 or results_ipv4
        else:
            return results_ipv4 or results_ipv6

    async def close(self):
        # 关闭 resolver 连接
        await self.resolver.nameserver.close()


# dns_map 配置：域名 -> (DNS服务器, 优先级)，支持泛域名
dns_map = {
    'dogyun.com': ('223.5.5.5', socket.AF_INET)
}
# 默认dns
default_dns = '1.1.1.1'
# 默认优先使用 IPv6
default_family = socket.AF_INET6
# 默认dns解析器
custom_resolver = CustomResolver(dns_map, default_dns, default_family)

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
