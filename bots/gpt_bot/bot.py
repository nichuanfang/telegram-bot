import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
import heapq
import io
import json
import mimetypes
from PIL import Image
import os
import re
import traceback
import cv2
import numpy as np

import regex
import requests
import telegram.helpers
from telegram import File, Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.constants import ParseMode
from telegram.ext import MessageHandler, ContextTypes, CallbackContext, CommandHandler, CallbackQueryHandler, filters

from bots.gpt_bot.gpt_platform import Platform
from my_utils import my_logging, bot_util
from my_utils.bot_util import auth, instantiate_platform, migrate_platform
from my_utils.document_util import DocumentHandler

# 获取日志
logger = my_logging.get_logger('gpt_bot')
# 正则
HASTE_SERVER_HOST_PATTERN = re.compile(
    rf'{re.escape(bot_util.HASTE_SERVER_HOST)}/(?:raw/)?([a-zA-Z]{{10}})(?:\.[a-zA-Z]+)?')
STOP_WORDS = frozenset({'的', '是', '在', '和', '了', '有',
                       '我', '也', '不', '就', '与', '他', '她', '它'})
# 默认平台
DEFAULT_PLATFORM_KEY = bot_util.DEFAULT_PLATFORM_KEY
# 面具列表
MASKS: dict = bot_util.masks
# 平台列表(非平台对象列表)
PLATFORMS: dict = bot_util.platforms
# 是否启用流式传输 默认不采用
ENABLE_STREAM = int(os.getenv('ENABLE_STREAM', False))


async def start(update: Update, context: CallbackContext) -> None:
    """启动方法

    Args:
        update (Update): 更新
        context (CallbackContext): _上下文_
    """
    start_message = (
        "欢迎使用！以下是您可以使用的命令列表：\n\n"
        "/clear - 清除聊天\n"
        "/masks - 切换面具\n"
        "/model - 切换模型\n"
        "/balance - 余额查询\n"
        "/platform - 切换平台\n"
        "/shop - 充值\n\n"
    )
    await update.message.reply_text(start_message)


def compress_question(question):
    # 使用 regex 库替代 re 库进行正则匹配
    question = regex.sub(r'\s+', ' ', question).strip()
    question_words = question.split()
    compressed_question = ' '.join(
        word for word in question_words if word not in STOP_WORDS)
    return compressed_question


@auth
async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_image_generator = context.user_data.get(
        'current_mask')['mask_key'] == 'image_generator'
    init_message_task = None
    if ENABLE_STREAM:
        message_text = '正在生成图片，请稍候...' if is_image_generator else '正在输入...'
        init_message_task = asyncio.create_task(
            update.message.reply_text(
                message_text, reply_to_message_id=update.message.message_id)
        )
    try:
        if update.message.text:
            content_task = asyncio.create_task(handle_code_or_url(update))
        elif update.message.photo or update.message.sticker:
            content_task = asyncio.create_task(
                handle_photo(update, context))
        elif update.message.audio or update.message.voice:
            content_task = asyncio.create_task(handle_audio(update, context))
        elif update.message.document:
            # gif虽然会被转为mp4 但是会被归类为document
            if update.message.document.mime_type.startswith('video'):
                # 视频处理
                content_task = asyncio.create_task(
                    handle_video(update, context))
            else:
                content_task = asyncio.create_task(
                    handle_document(update, context))
        elif update.message.video:
            content_task = asyncio.create_task(
                handle_video(update, context))
        else:
            raise ValueError('不支持的输入类型!')
        curr_mask = context.user_data.get(
            'current_mask')
        curr_mask['openai_completion_options'].update({
            "model": context.user_data.get('current_model')
        })
        if ENABLE_STREAM:
            await handle_stream_response(update, context, content_task, is_image_generator, init_message_task,
                                         **curr_mask['openai_completion_options'])
        else:
            await handle_response(update, context, content_task, is_image_generator,
                                  **curr_mask['openai_completion_options'])
    except Exception as e:
        await handle_exception(update, context, e, init_message_task)


async def handle_caption(update: Update, max_length):
    if update.message.caption:
        if len(update.message.caption.encode()) > max_length:
            raise ValueError(
                f'Your question is too long.请通过在线分享平台 {bot_util.HASTE_SERVER_HOST}  提问')
        handled_question = compress_question(update.message.caption.strip())
        return handled_question
    return None


def get_mime_type(image_path):
    mime_type, _ = mimetypes.MimeTypes.guess_type(image_path)
    return mime_type


async def handle_photo_download(update: Update, context: CallbackContext):
    # 判断是图片还是贴图
    if update.message.sticker:
        photo = update.message.sticker.thumbnail
    else:
        photo = update.message.photo[-2]

    photo_file: File = await context.bot.get_file(photo.file_id)
    image_data = await photo_file.download_as_bytearray()

    if not image_data:
        raise ValueError("Empty image data received.")

    # 将图片转换为 WebP 格式
    image = Image.open(io.BytesIO(image_data))
    webp_io = io.BytesIO()
    image.save(webp_io, format='WEBP')
    webp_data = webp_io.getvalue()

    return base64.b64encode(webp_data).decode("utf-8")


async def handle_photo(update: Update, context: CallbackContext):
    content = []
    current_platform: Platform = context.user_data['current_platform']
    current_model: str = context.user_data.get(
        'current_model')
    if not current_model.startswith(('gpt-4o', 'claude-3', 'gemini-1.5-pro')):
        raise ValueError(f'当前模型: {current_model}不支持图片解析!')
    # 并行处理 caption 和 photo download
    handle_result = await asyncio.gather(
        handle_caption(update, 3500),
        handle_photo_download(update, context)
    )

    caption_result = handle_result[0]
    image_base64 = handle_result[1]

    if current_platform.name == 'free_3':
        if caption_result:
            content.append(caption_result)
        if image_base64:
            content.append(f'data:image/webp;base64,{image_base64}')
    else:
        if caption_result:
            content.append({'type': 'text', 'text': caption_result})

        if image_base64:
            content.append({
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/webp;base64,{image_base64}'
                }
            })
    return content


async def handle_document_download(update: Update, context: CallbackContext):
    document = update.message.document
    file: File = await context.bot.get_file(document.file_id)
    document_bytes = await file.download_as_bytearray()
    return DocumentHandler.format(document_bytes, document.mime_type)


async def handle_document(update: Update, context: CallbackContext):
    handled_result = await asyncio.gather(handle_document_download(update, context),
                                          handle_caption(update, 3500))
    handle_document_result = handled_result[0]
    handle_caption_result = handled_result[1]
    return handle_document_result + (handle_caption_result if handle_caption_result else '')


async def handle_audio(update: Update, context: CallbackContext):
    current_platform: Platform = context.user_data['current_platform']
    audio_file = update.message.audio or update.message.voice
    if audio_file:
        file_id = audio_file.file_id
        new_file: File = await context.bot.get_file(file_id)
        ogg_path = os.path.join(f"temp/{file_id}.ogg")
        if 'whisper-1' not in current_platform.supported_models:
            raise RuntimeError(f'当前平台: {current_platform.name_zh}不支持语音输入!')
        else:
            await new_file.download_to_drive(ogg_path)
            content = {
                'type': 'audio',
                'audio_path': ogg_path
            }
        try:
            return content
        except Exception as e:
            raise ValueError(e)


async def analyse_video(update: Update, context: CallbackContext):
    content = []
    current_model: str = context.user_data.get(
        'current_model')
    if not current_model.startswith(('gpt-4o', 'claude-3', 'gemini-1.5-pro')):
        raise ValueError(f'当前模型: {current_model}不支持视频解析!')
    platform: Platform = context.user_data['current_platform']
    platform.chat.clear_messages(context)
    is_free_3 = (platform.name == 'free_3')
    if is_free_3:
        content.append('视频关键帧开始')
    else:
        content.append({
            'type': 'text',
            'text': '视频关键帧开始'
        })
    try:
        video_file = await context.bot.get_file(update.message.effective_attachment.file_id)
    except:
        raise RuntimeError('The video is too large!')
    video_path = f"temp/{video_file.file_id}.mp4"
    await video_file.download_to_drive(video_path)
    # Process the video
    key_frames = process_video(video_path)
    # Save key frames
    for _, frame in key_frames:
        mime_type = 'image/webp'
        _, buffer = cv2.imencode('.webp', frame)
        image_base64 = base64.b64encode(buffer).decode("utf-8")
        if platform.name == 'free_3':
            content.append(f'data:{mime_type};base64,{image_base64}')
        else:
            content.append({
                'type': 'image_url',
                'image_url': {
                    'url': f'data:{mime_type};base64,{image_base64}'
                }
            })
    # Clean up
    os.remove(video_path)
    if is_free_3:
        content.append('视频关键帧结束,请提供整个视频的综合分析')
    else:
        content.append({
            'type': 'text',
            'text': '视频关键帧结束'
        })
        content.append({
            'type': 'text',
            'text': '请提供整个视频的综合分析'
        })
    return content


async def handle_video(update: Update, context: CallbackContext):
    handled_result = await asyncio.gather(analyse_video(update, context),
                                          handle_caption(update, 3500))
    analyse_video_result = handled_result[0]
    handle_caption_result = handled_result[1]
    if handle_caption_result:
        current_platform: Platform = context.user_data['current_platform']
        if current_platform.name == 'free_3':
            analyse_video_result.append(handle_caption_result)
        else:
            analyse_video_result.append({
                'type': 'text',
                'text': handle_caption_result
            })
    return analyse_video_result


def calculate_diff(prev_frame, frame):
    diff = cv2.absdiff(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                       cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY))
    non_zero_count = np.count_nonzero(diff)
    total_pixels = diff.size
    diff_ratio = (non_zero_count / total_pixels) * 100
    return diff_ratio


def process_video(video_path):
    cap = cv2.VideoCapture(video_path)
    prev_frame = None
    frame_count = 0
    diff_ratios = []
    frames = []

    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []

        while True:
            success, frame = cap.read()
            if not success:
                break

            if prev_frame is not None:
                futures.append(executor.submit(
                    calculate_diff, prev_frame, frame))
                frames.append(frame)

            prev_frame = frame
            frame_count += 1

        for future in futures:
            diff_ratios.append(future.result())

    cap.release()

    # Determine a dynamic threshold based on the distribution of diff_ratios
    # For example, use the 90th percentile instead of 95th
    threshold = np.percentile(diff_ratios, 90)

    # Extract key frames based on the calculated diff_ratios
    key_frames = []
    for i, diff_ratio in enumerate(diff_ratios):
        if diff_ratio > threshold:
            if len(key_frames) < 10:
                heapq.heappush(key_frames, (diff_ratio, frames[i]))
            else:
                heapq.heappushpop(key_frames, (diff_ratio, frames[i]))

    # Sort key frames by diff_ratio in descending order
    key_frames.sort(reverse=True, key=lambda x: x[0])
    return key_frames


async def handle_code_or_url(update: Update):
    # 使用re模块搜索第一个匹配的URL
    match = HASTE_SERVER_HOST_PATTERN.search(update.message.text)
    if match:
        return await handle_code_url(update, match[1])
    else:
        return await handle_text(update)


async def handle_code_url(update: Update, code_id):
    response = requests.get(f'{bot_util.HASTE_SERVER_HOST}/raw/{code_id}')
    if response.status_code != 200 or len(response.text) == 0:
        raise ValueError(
            f'Your question url is Invalid.')
    return compress_question(response.text)


async def handle_text(update):
    if len(update.message.text.encode()) > 3500:
        raise ValueError(
            f'Your question is too long.请通过在线分享平台 {bot_util.HASTE_SERVER_HOST}  提问')
    content_text = update.effective_message.text.strip()
    content_text = compress_question(content_text)
    return content_text


async def handle_stream_response(update: Update, context: CallbackContext, content_task, is_image_generator: bool,
                                 init_message_task, **openai_completion_options):
    prev_answer = ''
    current_message_length = 0
    max_message_length = 3500
    message_content = ''
    need_notice = True
    gpt_platform: Platform = context.user_data['current_platform']
    ic_result = await asyncio.gather(init_message_task, content_task)
    init_message: Message = ic_result[0]
    current_message_id = init_message.message_id
    content = ic_result[1]
    async for status, curr_answer in gpt_platform.async_stream_request(content, context, **openai_completion_options):
        if is_image_generator:
            img_response = requests.get(curr_answer)
            if img_response.content:
                await asyncio.gather(
                    bot_util.edit_message(
                        update, context, current_message_id, True, '图片生成成功! 正在发送...'),
                    update.message.reply_photo(photo=img_response.content,
                                               reply_to_message_id=update.effective_message.message_id))
            continue
        if abs(len(curr_answer) - len(prev_answer)) < 100 and status != 'finished':
            continue
        new_content = curr_answer[len(prev_answer):]
        new_content_length = len(new_content)
        if current_message_length + new_content_length > max_message_length:
            if need_notice:
                await bot_util.edit_message(update, context, init_message.message_id, stream_ended=True, text="消息过长，内容正发往在线分享平台...")
                need_notice = False
            continue
        if new_content:
            message_content += new_content
            if message_content != prev_answer:
                await bot_util.edit_message(update, context, current_message_id, status == 'finished', message_content)
                current_message_length += new_content_length
        await asyncio.sleep(0.05)
        prev_answer = curr_answer
    if not need_notice:
        # 将剩余数据保存到在线代码分享平台
        response = requests.post(
            f'{bot_util.HASTE_SERVER_HOST}/documents', data=curr_answer.encode('utf-8'))
        if response.status_code == 200:
            result = response.json()
            document_id = result.get('key')
            if document_id:
                document_url = f'{bot_util.HASTE_SERVER_HOST}/raw/{document_id}.md'
                await bot_util.edit_message(update, context, init_message.message_id, True, text=f'请访问：{document_url}')
            else:
                await bot_util.edit_message(update, context, init_message.message_id, True, '保存到在线分享平台失败，请稍后重试。')


async def handle_response(update: Update, context: CallbackContext, content_task, is_image_generator, **openai_completion_options):
    await bot_util.send_typing(update)
    gpt_platform: Platform = context.user_data['current_platform']
    content = await content_task
    async for res in gpt_platform.async_request(content, context, **openai_completion_options):
        if res is None or len(res) == 0:
            continue
        if is_image_generator:
            # 将res的url下载 返回一个图片
            img_response = requests.get(res)
            if img_response.content:
                await update.message.reply_photo(photo=img_response.content,
                                                 reply_to_message_id=update.effective_message.message_id)
        else:
            if len(res.encode()) < 3500:
                await bot_util.send_message(update, res)
            else:
                response = requests.post(
                    f'{bot_util.HASTE_SERVER_HOST}/documents', data=res.encode('utf-8'))
                if response.status_code == 200:
                    result = response.json()
                    document_id = result.get('key')
                    if document_id:
                        # 谷歌浏览器需安装 Markdown Reader 极大的提升预览体验!
                        document_url = f'{bot_util.HASTE_SERVER_HOST}/raw/{document_id}.md'
                        await bot_util.send_message(update, text=f'消息过长，请通过在线分享平台访问：{document_url}')
                    else:
                        await bot_util.send_message(update, text='保存到在线分享平台失败，请稍后重试。')


async def handle_exception(update, context, e, init_message_task):
    logger.error(
        f"==================================================ERROR START==================================================================")
    # 记录异常信息
    logger.error(f"Exception occurred: {e}")
    traceback.print_exc()
    logger.error(
        f"==================================================ERROR END====================================================================")
    error_message = str(e)
    if hasattr(e, 'status_code') and getattr(e, 'status_code') == 401:
        current_platform: Platform = context.user_data['current_platform']
        if current_platform.name.startswith('free'):
            # free_1 | free_3    可能授权码/认证信息失效了
            # 移除临时配置文件中的相关key
            json_data = None
            with open(bot_util.TEMP_CONFIG_PATH, mode='r', encoding='utf-8') as f:
                json_data: dict = json.loads(f.read())
                if current_platform.name in json_data:
                    json_data[current_platform.name].pop('openai_api_key')
            if json_data:
                with open(bot_util.TEMP_CONFIG_PATH, mode='w+', encoding='utf-8') as f:
                    f.write(json.dumps(json_data, ensure_ascii=False))
                    # 刷新token成功!
            context.user_data['current_platform'] = instantiate_platform(
                current_platform.name)
            init_text = '授权信息已失效, 尝试重新获取,请稍后重试!\n\n'
        else:
            init_text = ''
    elif '上游负载已饱和' in error_message:
        current_platform: Platform = context.user_data['current_platform']
        current_platform.chat.clear_messages(context)
        init_text = '已达到token上限'
    elif 'at byte offset' in error_message:
        init_text = '缺少结束标记!\n\n'
    elif 'content_filter' in error_message:
        init_text = '内容被过滤!\n\n'
    elif '504 Gateway Time-out' in error_message:
        init_text = '网关超时!\n\n'
    else:
        init_text = ''
    try:
        if e.body and context.user_data['current_platform'].name != 'free_1':
            try:
                text = init_text + e.body['message'].split('(request', 1)[0]
            except:
                text = init_text + str(e.body)
        else:
            try:
                text = init_text + json.loads(e.args[0])['error']['message']
            except:
                text = init_text + json.loads(e.args[0])
    except:
        text = init_text + e.args[0]
    await exception_message_handler(update, context, init_message_task, text)


async def exception_message_handler(update, context, init_message_task, text):
    if init_message_task:
        init_message = await init_message_task
        await bot_util.edit_message(update, context, init_message.message_id, True, text)
    else:
        await bot_util.send_message(update, text)


@auth
async def balance_handler(update: Update, context: CallbackContext):
    await bot_util.send_typing(update)
    # 使用平台内置的方法查询余额
    platform: Platform = context.user_data['current_platform']
    try:
        balance_result = await platform.query_balance()
        await bot_util.send_message(update, balance_result)
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text(f'余额查询失败:\n\n {str(e)}', reply_to_message_id=update.message.message_id)


@auth
async def clear_handler(update: Update, context: CallbackContext):
    """
    清除上下文
    Args:
            update: 更新
            context:  上下文对象
    """
    # 创建内联按钮
    keyboard = [
        [InlineKeyboardButton("恢复上下文", callback_data='restore_context')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        '上下文已清除', reply_markup=reply_markup)
    # 清空历史消息
    context.user_data['current_platform'].chat.clear_messages(context)


async def restore_context_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="上下文已恢复")
    await context.user_data['current_platform'].chat.recover_messages(context)


def generate_mask_keyboard(masks, current_mask_key):
    keyboard = []
    row = []
    for i, mask_key in enumerate(masks):
        # 如果是当前选择的面具，添加标记
        mask_name = MASKS[mask_key]['name']
        if mask_key == current_mask_key:
            mask_name = "* " + mask_name
        row.append(InlineKeyboardButton(
            mask_name, callback_data=f'mask_key:{mask_key}'))
        if (i + 1) % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


@auth
async def masks_handler(update: Update, context: CallbackContext):
    """
    切换面具处理器
    Args:
            update:  更新对象
            context:  上下文对象
    """
    await bot_util.send_typing(update)
    # 获取当前选择的面具
    current_mask = context.user_data.get(
        'current_mask')
    current_mask_key = current_mask['mask_key']
    current_platform: Platform = context.user_data['current_platform']
    # 当前平台支持的面具列表
    masks = current_platform.supported_masks
    # 生成内联键盘
    keyboard = generate_mask_keyboard(
        masks, current_mask_key)
    await update.message.reply_text(
        '请选择一个面具:',
        reply_markup=keyboard
    )


async def mask_selection_handler(update: Update, context: CallbackContext):
    """
    处理面具选择
    Args:
            update:  更新对象
            context:  上下文对象
    """
    query = update.callback_query
    await query.answer()
    # 获取用户选择的面具 mask_key:{mask_key}
    selected_mask_key = query.data[9:]
    await query.edit_message_text(text=bot_util.escape_markdown_v2(
        MASKS[selected_mask_key]['introduction'], False), parse_mode=ParseMode.MARKDOWN_V2)
    # 当前平台
    current_platform: Platform = context.user_data['current_platform']
    # 面具实体 应用选择的面具
    selected_mask = context.user_data['current_mask'] = MASKS[selected_mask_key]

    # 根据所选择的面具 模型也要对应切换过去
    current_model = context.user_data['current_model']
    # 面具支持的模型
    mask_supported_models = current_platform.mask_model_mapping[selected_mask_key]
    if current_model not in mask_supported_models:
        context.user_data['current_model'] = mask_supported_models[0]

    # 根据选择的面具进行相应的处理
    current_platform.chat.set_max_message_count(
        selected_mask['max_message_count'])
    # 切换面具后清除上下文
    current_platform.chat.clear_messages(context)


# 生成模型选择键盘
def generate_model_keyboard(models, current_model):
    keyboard = []
    row = []

    for i, model in enumerate(models):
        # 如果是当前选择的模型，添加标记
        name = model
        if model == current_model:
            name = "* " + name
        row.append(InlineKeyboardButton(
            name, callback_data=f'model_key:{model}'))
        if (i + 1) % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


@auth
async def model_handler(update: Update, context: CallbackContext):
    """
    切换模型处理器
    Args:
            update:  更新对象
            context:  上下文对象
    """
    await bot_util.send_typing(update)
    # 获取当前的面具
    current_mask = context.user_data.get(
        'current_mask')
    platform: Platform = context.user_data['current_platform']
    # 当前面具支持的模型列表
    supported_models = platform.mask_model_mapping[current_mask['mask_key']]
    current_model = context.user_data.get('current_model')
    if current_model not in supported_models:
        current_model = context.user_data['current_model'] = supported_models[0]
    # 生成内联键盘
    keyboard = generate_model_keyboard(supported_models, current_model)

    await update.message.reply_text(
        '请选择一个模型:',
        reply_markup=keyboard
    )


async def model_selection_handler(update: Update, context: CallbackContext):
    """
    处理模型选择
    Args:
            update:  更新对象
            context:  上下文对象
    """
    query = update.callback_query
    await query.answer()
    # 获取用户选择的模型  model_key:
    selected_model = query.data[10:]
    await query.edit_message_text(
        text=f'模型已切换至*{bot_util.escape_markdown_v2(selected_model,False)}*',
        parse_mode=ParseMode.MARKDOWN_V2
    )
    # 应用选择的面具
    context.user_data['current_model'] = selected_model
    # 根据选择的模型进行相应的处理
    # 切换模型后清除上下文
    context.user_data['current_platform'].chat.clear_messages(context)


@auth
async def platform_handler(update: Update, context: CallbackContext):
    """
    切换平台处理器
    Args:
            update:  更新对象
            context:  上下文对象
    """
    await bot_util.send_typing(update)
    current_platform: Platform = context.user_data['current_platform']
    # 生成内联键盘
    keyboard = generate_platform_keyboard(
        update, context, current_platform)

    await update.message.reply_text(  # type: ignore
        '请选择一个平台:',
        reply_markup=keyboard
    )


def generate_platform_keyboard(update, context, current_platform: Platform):
    keyboard = []
    row = []
    if context.user_data['identity'] == 'user':
        for i, (key, platform) in enumerate(PLATFORMS.items()):
            # 如果是当前选择的面具，添加标记
            name = platform["name"]
            if key == current_platform.name:
                name = "* " + name
            row.append(InlineKeyboardButton(
                name, callback_data=f'platform_key:{key}'))
            if (i + 1) % 3 == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
    else:
        if current_platform.name == 'free_1':
            row.append(InlineKeyboardButton(
                '* 免费_1', callback_data='platform_key:free_1'))
            row.append(InlineKeyboardButton(
                '免费_2', callback_data='platform_key:free_2'))
            row.append(InlineKeyboardButton(
                '免费_3', callback_data='platform_key:free_3'))
        elif current_platform.name == 'free_2':
            row.append(InlineKeyboardButton(
                '免费_1', callback_data='platform_key:free_1'))
            row.append(InlineKeyboardButton(
                '* 免费_2', callback_data='platform_key:free_2'))
            row.append(InlineKeyboardButton(
                '免费_3', callback_data='platform_key:free_3'))
        elif current_platform.name == 'free_3':
            row.append(InlineKeyboardButton(
                '免费_1', callback_data='platform_key:free_1'))
            row.append(InlineKeyboardButton(
                '免费_2', callback_data='platform_key:free_2'))
            row.append(InlineKeyboardButton(
                '* 免费_3', callback_data='platform_key:free_3'))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


async def platform_selection_handler(update: Update, context: CallbackContext):
    """
    处理平台选择
    Args:
            update:  更新对象
            context:  上下文对象
    """
    query = update.callback_query
    await query.answer()
    # 获取用户选择的平台 platform_key:
    selected_platform_key = query.data[13:]
    await query.edit_message_text(
        text=f'平台已切换至[{bot_util.escape_markdown_v2(PLATFORMS[selected_platform_key]["name"])}]({bot_util.escape_markdown_v2(PLATFORMS[selected_platform_key]["index_url"])}) ',
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    current_platform: Platform = context.user_data['current_platform']
    # 当前的平台key
    current_platform_key = current_platform.name
    if selected_platform_key == current_platform_key:
        await query.edit_message_text(
            text=f'平台已切换至{current_platform.name_zh}')
        return
    # 解决切换平台可能带来的问题 比如当前面具在当前平台还在不在 ;  当前模型在当前平台可不可用
    current_mask = context.user_data['current_mask']
    # 判断所选平台是否支持这些面具

    supported_masks = PLATFORMS[selected_platform_key]['supported_masks']
    # todo 如果面具不支持 就设置为第一个面具
    if current_mask['mask_key'] not in supported_masks:
        current_mask = context.user_data['current_mask'] = MASKS[supported_masks[0]]

    # 处理模型切换
    current_model = context.user_data['current_model']
    # 判断当前平台是否支持这个模型
    mask_model_mapping = PLATFORMS[selected_platform_key]['mask_model_mapping']
    # 上面更改后的面具支持的模型列表 和平台自带的supported_models不同 那个是平台层面的模型可用性 跟面具层面的不一样
    mask_supported_models = mask_model_mapping[current_mask['mask_key']]
    # todo 如果模型不支持 就设置为第一个模型
    if current_model not in mask_supported_models:
        context.user_data['current_model'] = mask_supported_models[0]

    # 切换平台 需要转移平台的状态(api-key更改 历史消息迁移)
    context.user_data['current_platform'] = await migrate_platform(from_platform=current_platform, to_platform_key=selected_platform_key,
                                                                   context=context, max_message_count=current_mask['max_message_count'])


@auth
async def shop_handler(update: Update, context: CallbackContext):
    if context.user_data['identity'] == 'user':
        platform = context.user_data['current_platform']
        # 创建一个包含 URL 按钮的键盘
        keyboard = [[InlineKeyboardButton(
            "Visit Shop", url=platform.payment_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # 发送带有图片、描述和 URL 按钮的消息
        await update.message.reply_text(text='Click the button below to visit the shop:', reply_markup=reply_markup)


def handlers():
    return [
        CommandHandler('start', start),
        CommandHandler('clear', clear_handler),
        CommandHandler('masks', masks_handler),
        CommandHandler('model', model_handler),
        CommandHandler('balance', balance_handler),
        CommandHandler('platform', platform_handler),
        CommandHandler('shop', shop_handler),
        CallbackQueryHandler(mask_selection_handler,
                             pattern='^mask_key:'),
        CallbackQueryHandler(model_selection_handler,
                             pattern='^model_key:'),
        CallbackQueryHandler(restore_context_handler,
                             pattern='^restore_context$'),
        CallbackQueryHandler(platform_selection_handler,
                             pattern='^platform_key:'),
        MessageHandler(
            filters.TEXT & ~filters.COMMAND | filters.ATTACHMENT, answer)
    ]
