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

# 复制项目文件到工作目录
COPY . .

# 安装Python依赖
RUN pip install --upgrade pip \
    && pip install -r requirements.txt --no-cache-dir

# 设置启动命令
CMD ["python", "app.py"]
