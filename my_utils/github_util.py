import json
import os
import aiohttp


async def trigger_github_workflow(session: aiohttp.ClientSession, repo: str, event_type: str, client_payload=None):
    """触发github workflow

    Args:
            repo (str): 仓库名
            event_type (str): 事件类型
            client_payload (dict): 负载
    """
    if client_payload is None:
        client_payload = {}
    GH_TOKEN = os.environ["BOT_GITHUB_TOKEN"]
    if not GH_TOKEN:
        raise Exception("BOT_GITHUB_TOKEN未设置!")
    header = {
        'Accept': 'application/vnd.github.everest-preview+json',
        'Authorization': f'token {GH_TOKEN}'
    }
    data = json.dumps({"event_type": f"{event_type}",
                       "client_payload": client_payload})
    return await session.post(f'https://api.github.com/repos/nichuanfang/{repo}/dispatches', data=data, headers=header)
