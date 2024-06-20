import asyncio
import base64
import json
import os
import re
import traceback

import httpx
import telegram.helpers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.constants import ParseMode
from telegram.ext import MessageHandler, ContextTypes, CallbackContext, CommandHandler, CallbackQueryHandler, filters

from bots.gpt_bot.gpt_platform import Platform
from my_utils import my_logging, bot_util
from my_utils.bot_util import auth, migrate_platform

# 获取日志
logger = my_logging.get_logger('gpt_bot')
# 默认面具
DEFAULT_MASK_KEY: str = bot_util.DEFAULT_MASK_KEY
# 默认平台
DEFAULT_PLATFORM_KEY = bot_util.DEFAULT_PLATFORM_KEY
# 面具列表
MASKS = bot_util.masks
# 平台列表(非平台对象列表)
PLATFORMS = bot_util.platforms
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
    # 去除多余的空格和换行符
    question = re.sub(r'\s+', ' ', question).strip()

    # 删除停用词（这里只是一个简单示例，可以根据需要扩展）
    stop_words = {'的', '是', '在', '和', '了', '有',
                  '我', '也', '不', '就', '与', '他', '她', '它'}
    question_words = question.split()
    compressed_question = ' '.join(
        [word for word in question_words if word not in stop_words])

    return compressed_question


@auth
async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and context.user_data
    is_image_generator = context.user_data.get(
        'current_mask', MASKS[DEFAULT_MASK_KEY])['name'] == '图像生成助手'
    init_message_task = None
    if ENABLE_STREAM:
        message_text = '正在生成图片，请稍候...' if is_image_generator else '正在输入...'
        init_message_task = asyncio.create_task(
            update.message.reply_text(
                message_text, reply_to_message_id=update.message.message_id)
        )
    max_length = 4096
    try:
        if update.message.text:
            content_task = asyncio.create_task(handle_text(update, max_length))
        elif update.message.photo:
            content_task = asyncio.create_task(
                handle_photo(update, context, max_length))
        elif update.message.document:
            content_task = asyncio.create_task(
                handle_document(update, context, max_length))
        elif update.message.audio or update.message.voice:
            content_task = asyncio.create_task(handle_audio(update, context))
        elif update.message.video:
            content_task = asyncio.create_task(handle_video(update, context))
        else:
            raise ValueError('不支持的输入类型!')
        curr_mask = context.user_data.get(
            'current_mask', MASKS[DEFAULT_MASK_KEY])
        content_result = await content_task
        curr_mask['openai_completion_options'].update({
            "model": context.user_data.get('current_model', curr_mask['default_model'])
        })
        if ENABLE_STREAM:
            await handle_stream_response(update, context, content_result, is_image_generator, init_message_task,
                                         **curr_mask['openai_completion_options'])
        else:
            await handle_response(update, context, content_result, is_image_generator,
                                  **curr_mask['openai_completion_options'])
    except Exception as e:
        await handle_exception(update, context, e, init_message_task)


async def handle_caption(update: Update, max_length):
    if update.message.caption:
        handled_question = compress_question(update.message.caption.strip())
        if len(handled_question) > max_length:
            raise ValueError(
                f'Your question is too long. Please limit it to {max_length} characters.')
        return handled_question
    return None


def get_mime_type(image_path):
    if image_path.endswith(".jpg") or image_path.endswith(".jpeg"):
        return "image/jpeg"
    elif image_path.endswith(".png"):
        return "image/png"
    elif image_path.endswith(".webp"):
        return "image/webp"
    elif image_path.endswith(".gif"):
        return "image/gif"
    else:
        print(
            f"Unsupported image format. Please use a .jpg, .jpeg, .png, .webp, or .gif image file.")
        exit()


async def handle_photo_download(update: Update, context: CallbackContext):
    photo = update.message.photo[-2]
    photo_file = await context.bot.get_file(photo.file_id)
    async with httpx.AsyncClient() as client:
        photo_response = await client.get(photo_file.file_path)
    image_data = photo_response.content
    # mime类型
    mime_type = get_mime_type(photo_file.file_path)
    if image_data:
        return mime_type, base64.b64encode(image_data).decode("utf-8")
    else:
        raise ValueError("Empty image data received.")


async def handle_photo(update: Update, context: CallbackContext, max_length):
    content = []
    current_mask = context.user_data.get(
        'current_mask', MASKS[DEFAULT_MASK_KEY])
    current_model: str = context.user_data.get(
        'current_model', current_mask['default_model'])
    if not current_model.startswith(('gpt-4o', 'claude-3')):
        raise ValueError(f'当前模型: {current_model}不支持图片解析!')

    handle_result = await asyncio.gather(handle_caption(update, max_length),
                                         handle_photo_download(update, context))
    caption_result = handle_result[0]
    mime_type, image_base64 = handle_result[1]
    if caption_result:
        content.append({'type': 'text', 'text': caption_result})
    if image_base64:
        content.append({'type': 'image_url', 'image_url': {
                       'url': f'data:{mime_type};base64,{image_base64}'}})
    return content


async def handle_document_download(update: Update, context: CallbackContext):
    document = update.message.document
    file = await context.bot.get_file(document.file_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(file.file_path)
    document_text = response.text
    return f'```{document.mime_type}\n{document_text}\n```\n'


async def handle_document(update: Update, context: CallbackContext, max_length):
    handled_result = await asyncio.gather(handle_document_download(update, context),
                                          handle_caption(update, max_length))
    handle_document_result = handled_result[0]
    handle_caption_result = handled_result[1]
    return handle_document_result + (handle_caption_result if handle_caption_result else '')


async def handle_audio(update: Update, context: CallbackContext):
    audio_file = update.message.audio or update.message.voice
    if audio_file:
        file_id = audio_file.file_id
        new_file = await context.bot.get_file(file_id)
        ogg_path = os.path.join(f"{file_id}.ogg")
        await new_file.download_to_drive(ogg_path)
        try:
            return {
                'type': 'audio',
                'audio_path': ogg_path
            }
        except Exception as e:
            raise ValueError(e)


async def handle_video(update, context):
    return "Video processing is not implemented yet."


async def handle_text(update, max_length):
    content_text = update.effective_message.text.strip()
    content_text = compress_question(content_text)
    if len(content_text) > max_length:
        raise ValueError(
            f'Your question is too long. Please limit it to {max_length} characters.')
    return content_text


async def handle_stream_response(update: Update, context: CallbackContext, content: str, is_image_generator: bool,
                                 init_message_task, **openai_completion_options):
    prev_answer = ''
    current_message_length = 0
    max_message_length = 4096
    message_content = ''
    gpt_platform: Platform = context.user_data['current_platform']
    init_message: Message = await init_message_task
    current_message_id = init_message.message_id
    async for status, curr_answer in gpt_platform.async_stream_request(content, **openai_completion_options):
        if is_image_generator:
            async with httpx.AsyncClient() as client:
                img_response = await client.get(curr_answer)
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
            new_init_message = await context.bot.send_message(chat_id=update.message.chat_id, text='正在输入...')
            current_message_id = new_init_message.message_id
            current_message_length = 0
            message_content = ''
        if new_content:
            message_content += new_content
            if message_content != prev_answer:
                await bot_util.edit_message(update, context, current_message_id, status == 'finished', message_content)
                current_message_length += new_content_length
        await asyncio.sleep(0.05)
        prev_answer = curr_answer


async def handle_response(update, context, content, is_image_generator, **openai_completion_options):
    await bot_util.send_typing(update)
    gpt_platform: Platform = context.user_data['current_platform']
    async for res in gpt_platform.async_request(content, **openai_completion_options):
        if res is None or len(res) == 0:
            continue
        if is_image_generator:
            async with httpx.AsyncClient() as client:
                # 将res的url下载 返回一个图片
                img_response = await client.get(res)
            if img_response.content:
                await update.message.reply_photo(photo=img_response.content,
                                                 reply_to_message_id=update.effective_message.message_id)
        else:
            if len(res) < 4096:
                await bot_util.send_message(update, res)
            else:
                parts = [res[i:i + 4096] for i in range(0, len(res), 4096)]
                for part in parts:
                    await bot_util.send_message(update, part)


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
        # free_1可能授权码失效了
        context.user_data['current_platform'] = migrate_platform(
            context.user_data['current_platform'], 'free_1', 4)
        init_text = 'free_1授权码已更新\n\n'
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
    task = asyncio.create_task(update.message.reply_text(
        '上下文已清除', reply_markup=reply_markup))
    # 清空历史消息
    context.user_data['current_platform'].chat.clear_messages(context)
    await task

# 处理按钮点击事件


async def restore_context_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    task = asyncio.create_task(query.edit_message_text(text="上下文已恢复"))
    context.user_data['current_platform'].chat.recover_messages(context)
    await task


def generate_mask_keyboard(masks, current_mask_key, is_free: bool):
    keyboard = []
    row = []
    if is_free:
        if current_mask_key not in masks:
            for i, mask_key in enumerate(masks):
                # 如果是当前选择的面具，添加标记
                name = MASKS[mask_key]['name']
                if i == 0:
                    name = "* " + name
                row.append(InlineKeyboardButton(
                    name, callback_data=f'mask_key:{mask_key}'))
                if (i + 1) % 2 == 0:
                    keyboard.append(row)
                    row = []
        else:
            for i, mask_key in enumerate(masks):
                # 如果是当前选择的面具，添加标记
                name = MASKS[mask_key]['name']
                if mask_key == current_mask_key:
                    name = "* " + name
                    flag = True
                row.append(InlineKeyboardButton(
                    name, callback_data=f'mask_key:{mask_key}'))
                if (i + 1) % 2 == 0:
                    keyboard.append(row)
                    row = []
    else:
        for i, (key, mask) in enumerate(masks.items()):
            # 如果是当前选择的面具，添加标记
            name = mask["name"]
            if key == current_mask_key:
                name = "* " + name
            row.append(InlineKeyboardButton(
                name, callback_data=f'mask_key:{key}'))
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
        'current_mask', MASKS[DEFAULT_MASK_KEY])
    current_mask_key = current_mask['mask_key']

    # 免费的模型和收费的模型 masks不同
    current_platform: Platform = context.user_data['current_platform']
    # 当前的平台key
    current_platform_key = current_platform.name
    if current_platform_key.startswith('free'):
        is_free = True
        masks = list(PLATFORMS[current_platform_key]
                     ['mask_model_mapping'].keys())
    else:
        masks = MASKS
        is_free = False
    # 生成内联键盘
    keyboard = generate_mask_keyboard(
        masks, current_mask_key, is_free)
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
    # 面具实体 应用选择的面具
    selected_mask = context.user_data['current_mask'] = MASKS[selected_mask_key]
    # 选择当前模型
    current_model = context.user_data.get('current_model')
    #     'current_model', selected_mask['default_model'])
    # 当前平台
    curr_platform: Platform = context.user_data['current_platform']
    # 获取当前模型  如果当前模型兼容选择的面具 则无需切换模型; 如果不兼容 则需切换到该面具的默认模型
    if curr_platform.name.startswith('free'):
        supported_models = PLATFORMS[curr_platform.name]['supported_models']
        if current_model:
            if current_model not in supported_models:
                context.user_data['current_model'] = supported_models[0]
        else:
            context.user_data['current_model'] = supported_models[0]
    else:
        if current_model:
            if current_model not in selected_mask['supported_models']:
                context.user_data['current_model'] = selected_mask['default_model']
        else:
            context.user_data['current_model'] = selected_mask['default_model']

    # 根据选择的面具进行相应的处理
    switch_success_message_task = asyncio.create_task(query.edit_message_text(
        text=bot_util.escape_markdown_v2(selected_mask['introduction']),
        parse_mode=ParseMode.MARKDOWN_V2
    ))
    curr_platform.chat.set_max_message_count(
        4 if curr_platform.name.startswith('free') else selected_mask['max_message_count'])
    # 切换面具后清除上下文
    curr_platform.chat.clear_messages(context)
    await switch_success_message_task


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
        'current_mask', MASKS[DEFAULT_MASK_KEY])
    platform: Platform = context.user_data['current_platform']
    if platform.name.startswith('free'):
        supported_models = PLATFORMS[platform.name]['supported_models']
        current_model = context.user_data.get(
            'current_model', supported_models[0])
        if current_model not in supported_models:
            current_model = supported_models[0]
            context.user_data['current_model'] = current_model
    else:
        supported_models = current_mask['supported_models']
        if context.user_data.get('current_model') not in supported_models:
            current_model = supported_models[0]
            context.user_data['current_model'] = current_model
        else:
            # 获取当前选择的模型
            current_model = context.user_data.get('current_model')
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
    # 应用选择的面具
    context.user_data['current_model'] = selected_model
    # 根据选择的模型进行相应的处理
    switch_model_task = asyncio.create_task(query.edit_message_text(
        text=f'模型已切换至*{telegram.helpers.escape_markdown(selected_model, version=2)}*',
        parse_mode=ParseMode.MARKDOWN_V2
    ))
    # 切换模型后清除上下文
    context.user_data['current_platform'].chat.clear_messages(context)
    await switch_model_task


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
    current_platform: Platform = context.user_data['current_platform']
    # 当前的平台key
    current_platform_key = current_platform.name
    if selected_platform_key == current_platform_key:
        await query.edit_message_text(
            text=f'平台已切换至*{telegram.helpers.escape_markdown(current_platform.name_zh, version=2)}*',
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    # 解决切换平台可能带来的问题 比如当前面具在当前平台还在不在 ;  当前模型在当前平台可不可用
    if 'current_mask' not in context.user_data:
        current_mask = context.user_data['current_mask'] = MASKS[DEFAULT_MASK_KEY]
    else:
        current_mask = context.user_data['current_mask']
        # 判断所选平台是否支持这些面具
        if selected_platform_key.startswith('free'):
            mask_model_mapping = PLATFORMS[selected_platform_key]['mask_model_mapping']
            # todo 如果面具不支持 就设置为第一个面具
            if current_mask['mask_key'] not in mask_model_mapping.keys():
                default_mask_key = list(mask_model_mapping.keys())[0]
                current_mask = context.user_data['current_mask'] = MASKS[default_mask_key]
        else:
            # 剩余的都是收费的平台 支持所有面具
            current_mask = context.user_data['current_mask']

    # 处理模型切换
    if 'current_model' not in context.user_data:
        # 如果此时会话中未存储当前模型 初始化一个当前面具的默认模型
        current_model = context.user_data['current_model'] = current_mask['default_model']
    else:
        # 当前模型
        current_model = context.user_data['current_model']
        # 判断当前平台是否支持这个模型
        if selected_platform_key.startswith('free'):
            supported_models = PLATFORMS[selected_platform_key]['supported_models']
            # todo 如果模型不支持 就设置为第一个模型
            if current_model not in supported_models:
                default_model = supported_models[0]
                context.user_data['current_model'] = default_model
        else:
            # 有可能免费平台的收费平台不支持 比如'claude-3-haiku-20240307'
            if current_model not in current_mask['supported_models']:
                context.user_data['current_model'] = current_mask['default_model']

    # 切换平台 需要转移平台的状态(api-key更改 历史消息迁移)
    new_platform = context.user_data['current_platform'] = migrate_platform(from_platform=current_platform, to_platform_key=selected_platform_key,
                                                                            max_message_count=current_mask['max_message_count'])
    switch_message = f'平台已切换至[{bot_util.escape_markdown_v2(new_platform.name_zh)}]({bot_util.escape_markdown_v2(new_platform.index_url)}) '

    await query.edit_message_text(
        text=switch_message,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


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
