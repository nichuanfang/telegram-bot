""" 计算token消耗的工具 """
import tiktoken

# 编码器
encoder = tiktoken.get_encoding('cl100k_base')


def count_token(content: str):
    """ 计算单条内容的token """
    return len(encoder.encode(content))


def count_tokens(messages: list[dict]):
    """ 计算总消息的token """
    total_tokens = 0
    for message in messages:
        # 每个消息的 token 数
        message_tokens = encoder.encode(message['content'])
        total_tokens += len(message_tokens)

    return total_tokens


if __name__ == '__main__':
    # 示例消息历史
    messages = [
        "你好！你今天怎么样？",
        "我很好，谢谢！你呢？",
        "我也很好。有什么可以帮你的吗？"
    ]

    # 计算总 token 数
    total_tokens = count_tokens(messages)
    print(f"总共消耗的 token 数: {total_tokens}")
