import os

from my_utils.my_logging import get_logger

logger = get_logger('validation_util')


# 校验环境变量
def validate(*keys):
    values = []
    for keyword in keys:
        env = os.environ.get(keyword)
        if env is None or env == '':
            logger.error(f'{keyword}未设置!')
            raise ValueError(f'{keyword}未设置!')
        values.append(env)
    return values
