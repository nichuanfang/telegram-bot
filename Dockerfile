# 第一阶段：构建阶段
FROM python:3.11-alpine as builder

# 设置环境变量
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# 安装必要的构建工具和编译器
RUN apk --no-cache add \
    ffmpeg \
    build-base \
    cmake \
    ninja \
    && pip install --upgrade pip

# 设置工作目录
WORKDIR /app

# 复制项目文件到工作目录
COPY . .

# 安装Python依赖
RUN pip install -r requirements.txt --no-cache-dir

# 第二阶段：运行阶段
FROM python:3.11-alpine

# 设置环境变量
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# 安装ffmpeg
RUN apk --no-cache add ffmpeg

# 设置工作目录
WORKDIR /app

# 复制构建阶段的依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制项目文件到工作目录
COPY . .

# 设置启动命令
CMD ["python", "app.py"]
