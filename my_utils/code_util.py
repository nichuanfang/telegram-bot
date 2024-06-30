# 跟代码相关的工具类

import re

# 增加更多语言和配置文件特征以提高检测准确率
LANGUAGE_PATTERNS = {
    'Python': [r'\bdef\b', r'\bimport\b', r'\bprint\b', r'\bself\b'],
    'Java': [r'\bpublic\b', r'\bclass\b', r'\bvoid\b', r'\bSystem\.out\.println\b'],
    'JavaScript': [r'\bfunction\b', r'\bconst\b', r'\bvar\b', r'\bconsole\.log\b'],
    'Go': [r'\bpackage\b', r'\bfunc\b', r'\bimport\b', r'\bfmt\b'],
    'C++': [r'#include\b', r'\busing namespace\b', r'\bstd\b', r'\bcout\b'],
    'Ruby': [r'\bdef\b', r'\bend\b', r'\bputs\b'],
    'PHP': [r'<\?php', r'\becho\b', r'\bfunction\b'],
    'Swift': [r'\bimport\b', r'\bclass\b', r'\bfunc\b'],
    'Kotlin': [r'\bfun\b', r'\bval\b', r'\bclass\b'],
    'Bash': [r'#!/bin/bash', r'\becho\b', r'\bif\b'],
    'CSS': [r'\bbody\b', r'\bmargin\b', r'\bpadding\b'],
    'JSON': [r'\{', r'\}', r'\b":\b'],
    'HTML': [r'<\w+', r'</\w+>', r'<!--', r'-->'],
    'YAML': [r'^\s*\w+:\s*', r'^\s*-\s+\w+'],
    '.env': [r'^\w+=', r'^\w+:\s*\w+'],
    'properties': [r'^\w+\.\w+=', r'^\w+='],
    'Dockerfile': [r'^FROM\b', r'^RUN\b', r'^CMD\b', r'^EXPOSE\b']
}

# 常见编程语言关键字集合
CODE_KEYWORDS = {
    'class', 'def', 'import', 'from', 'return', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'finally',
    'public', 'private', 'protected', 'static', 'void', 'int', 'float', 'double', 'char', 'boolean', 'package',
    'const', 'let', 'function', 'var'
}
# 常见代码符号集合
CODE_SYMBOLS = {'{', '}', '(', ')', ';', '#', '//', '/*', '*/', '"""', "'''"}


def is_code_block(text):
    # 检查字符串是否符合任何一种语言或配置文件的代码特征
    for _, patterns in LANGUAGE_PATTERNS.items():
        matches = 0
        for pattern in patterns:
            if re.search(pattern, text, re.MULTILINE):
                matches += 1
                if matches >= 2:
                    return True

    # 检查是否有多行，并且每行有缩进
    lines = text.split('\n')
    if len(lines) > 1:
        indented_lines = [
            line for line in lines if line.startswith((' ', '\t'))]
        if len(indented_lines) > 0:
            return True

    # 检查字符串是否包含常见的代码符号
    code_symbols = ['{', '}', '(', ')', '[', ']', '==', '!=',
                    '<=', '>=', '=', '+', '-', '*', '/', '%', '->', ':']
    for symbol in code_symbols:
        if symbol in text:
            return True

    return False


# 示例的detect_language函数
def detect_language(code):
    """ 简单的语言检测函数 """
    for language, patterns in LANGUAGE_PATTERNS.items():
        matches = 0
        for pattern in patterns:
            if re.search(pattern, code, re.MULTILINE):
                matches += 1
                if matches >= 2:
                    return language
    return 'Generic'  # 默认情况


def compress_code(code, language: str = None):
    """ 压缩代码块 """
    if not language:
        language = detect_language(code)

    # 通用处理：去除多行注释和单行注释
    if language in {'Java', 'JavaScript', 'Go', 'C++', 'C#', 'PHP', 'Swift', 'Kotlin'}:
        code = re.sub(r'/\*[\s\S]*?\*/', '', code)
        code = re.sub(r'//.*', '', code)
    elif language in {'Python', 'Ruby', 'Bash'}:
        code = re.sub(r'#.*', '', code)
        if language == 'Python':
            code = re.sub(r'"""[\s\S]*?"""', '', code)
            code = re.sub(r"'''[\s\S]*?'''", '', code)
        elif language == 'Bash':
            code = re.sub(r': ?<<\w+[\s\S]*?\w+', '', code)
    elif language == 'CSS':
        code = re.sub(r'/\*[\s\S]*?\*/', '', code)
    elif language == 'HTML':
        code = re.sub(r'<!--[\s\S]*?-->', '', code)  # 去除HTML注释
    elif language == 'YAML':
        code = re.sub(r'#.*', '', code)  # 去除YAML注释
    elif language == '.env':
        code = re.sub(r'#.*', '', code)  # 去除env文件注释
    elif language == 'properties':
        code = re.sub(r'#.*', '', code)  # 去除properties文件注释
    elif language == 'Dockerfile':
        code = re.sub(r'#.*', '', code)  # 去除Dockerfile注释

    # 语言特定处理
    if language == 'Python':
        code = re.sub(r'def (\w+)\((.*?)\):\s*return (.*)',
                      r'\1 = lambda \2: \3', code)
    elif language == 'JavaScript':
        code = re.sub(
            r'function (\w+)\((.*?)\)\s*{([^{}]*)}', r'const \1 = (\2) => {\3}', code)
    elif language in {'Java', 'C++', 'C#'}:
        code = re.sub(r'class (\w+)\s*{([^{}]*)}', r'class \1 {\2}', code)
    elif language == 'HTML':
        code = re.sub(r'>\s+<', '><', code)  # 去除标签之间的多余空白

    # 通用处理：去除多余的空白和换行符
    code = re.sub(r'\s+', ' ', code).strip()

    # 保留必要的结构
    if language in {'Java', 'JavaScript', 'C++', 'C#', 'Go', 'PHP', 'Swift', 'Kotlin', 'CSS'}:
        code = code.replace('; ', ';').replace(' {', '{').replace(' }', '}')

    # JSON特定处理：去除所有空白字符
    if language == 'JSON':
        code = re.sub(r'\s+', '', code)

    # 通用兜底处理
    if language == 'Generic':
        code = re.sub(r'/\*[\s\S]*?\*/', '', code)  # 去除C风格注释
        code = re.sub(r'#.*', '', code)             # 去除Shell/Python/Ruby风格注释
        code = re.sub(r'\s+', ' ', code).strip()    # 去除多余的空白和换行符

    return code
