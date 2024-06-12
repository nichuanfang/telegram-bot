FROM python:3.11-slim

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

RUN apt-get update && apt-get install -y ffmpeg&& apt-get clean

WORKDIR /app

# 复制应用代码
COPY . .

# 安装Python依赖项
RUN pip install -r requirements.txt --no-cache-dir

#安装 openai-whisper
#RUN pip install torch==2.3.1+cpu -f https://download.pytorch.org/whl/torch_stable.html && \
#    pip install openai-whisper --no-deps && \
#    pip install -r requirements-whisper.txt --no-cache-dir

# 设置默认命令
CMD ["python", "app.py"]
