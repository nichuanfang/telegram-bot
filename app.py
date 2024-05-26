import asyncio
import os

import dotenv

dotenv.load_dotenv()

# 获取 bots 目录下的所有子目录
bot_directories = [d for d in os.listdir('bots') if os.path.isdir(os.path.join('bots', d))]


async def start_bot_async(bot_module):
	start_function = getattr(bot_module, 'start_bot')
	await start_function()


async def periodic_execution(periodic_module):
	periodic_task = getattr(periodic_module, 'periodic_task')
	await periodic_task()


async def main():
	tasks = []
	# 动态加载每个机器人
	for bot_directory in bot_directories:
		try:
			# 动态导入每个机器人的 bootstrap 模块  同时指明了需要导入的属性(函数,子模块等)
			bot_module = __import__(f'bots.{bot_directory}.bootstrap', fromlist=['start_bot'])
			
			# todo 如果模块是dogyun 则还要添加定时任务
			if bot_directory == 'dogyun_bot':
				periodic_module = __import__(f'bots.{bot_directory}.periodic_task', fromlist=['periodic_task'])
				tasks.append(periodic_execution(periodic_module))
			
			# 将启动函数添加到任务列表中
			tasks.append(start_bot_async(bot_module))
		except ImportError as e:
			print(f"Failed to import bot {bot_directory}: {e}")
	
	# 异步执行所有启动函数
	await asyncio.gather(*tasks)


# 运行异步主函数
asyncio.run(main())
