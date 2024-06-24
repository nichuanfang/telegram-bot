import os
import redis


def create_redis_pool() -> redis.ConnectionPool:
    # 获取redis连接池
    redis_address = os.getenv('REDIS_HOST')
    redis_port = os.getenv('REDIS_PORT')
    redis_password = os.getenv('REDIS_PASSWORD')

    redis_pool = redis.ConnectionPool(
        host=redis_address,
        port=redis_port,
        password=redis_password,
        decode_responses=True
    )
    return redis_pool


def close_redis_pool(redis_pool: redis.ConnectionPool):
    # 关闭连接池
    redis_pool.close()


def get_redis_client(redis_pool: redis.ConnectionPool):
    # 获取redis客户端
    return redis.StrictRedis(connection_pool=redis_pool, encoding='utf-8')


def get(redis_client: redis.StrictRedis, key):
    """ 获取值 """
    return redis_client.get(key)


def set(redis_client: redis.StrictRedis, key, value, expire):
    """ 设置值 """
    redis_client.set(key, value, expire)
