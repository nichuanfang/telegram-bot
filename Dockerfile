# 第一阶段：构建环境
FROM python:3.11-slim AS build

# 设置环境变量
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# 更新包列表并安装构建依赖项
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        libjpeg-dev \
        libpng-dev \
        libtiff-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libv4l-dev \
        libxvidcore-dev \
        libx264-dev \
        libatlas-base-dev \
        gfortran \
        pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制项目文件到工作目录
COPY . .

# 安装 Python 依赖
RUN pip install --upgrade pip && pip install -r requirements.txt --no-cache-dir

# 第二阶段：运行环境
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# 安装运行时必要的依赖项
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libjpeg62-turbo \
        libpng16-16 \
        libtiff5 \
        libavcodec58 \
        libavformat58 \
        libswscale5 \
        libv4l-0 \
        libxvidcore4 \
        libx264-155 \
        libatlas3-base \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 从构建阶段复制安装好的 Python 依赖
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# 复制项目文件到工作目录
COPY . .

# 设置启动命令
CMD ["python", "app.py"]
