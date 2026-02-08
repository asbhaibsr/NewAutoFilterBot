import os
import logging
import random
import asyncio
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait, PeerIdInvalid, ChannelInvalid, MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from database.ia_filterdb import Media, get_file_details, unpack_new_file_id
from database.users_chats_db import db
from info import CHANNELS, ADMINS, AUTH_CHANNEL, LOG_CHANNEL, PICS, BATCH_FILE_CAPTION, CUSTOM_FILE_CAPTION, PROTECT_CONTENT, REQUEST_CHANNEL, BOT_PM_USERNAME
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from database.connections_mdb import active_connection
import re
import json
import base64

logger = logging.getLogger(__name__)

BATCH_FILES = {}

BOTS_PAGES = [
    # Page 0
    (
        "**🎬 पहला मूवी डाउनलोड बॉट**\n\n"
        "यह बॉट आपको आसानी से मूवी खोजने और डाउनलोड करने में मदद करता है।\n\n"
        "➔ **बॉट लिंक:** @asfilter_bot"
    ),
    # Page 1
    (
        "**🎞️ दूसरा मूवी डाउनलोड बॉट**\n\n"
        "आपकी मूवी खोजने की ज़रूरतों के लिए एक और बेहतरीन बॉट।\n\n"
        "➔ **बॉट लिंक:** @AsMoviesSearch_roBot"
    ),
    # Page 2
    (
        "**💬 एआई चैट बॉट**\n\n"
        "यह एक सेल्फ-लर्निंग एआई चैट बॉट है जो ग्रुप में बहुत समझदारी से बात कर सकता है।\n\n"
        "➔ **बॉट लिंक:** @askiangelbot"
    ),
    # Page 3
    (
        "**💰 कमाई करने वाला बॉट**\n\n"
        "इस बॉट को रेफर करें और जब लोग आपके ग्रुप में आएंगे, तो यह बॉट यूजर को पैसे देगा।\n\n"
        "➔ **बॉट लिंक:** @LinkProviderRobot"
    ),
    # Page 4
    (
        "**🧑‍💻 ओनर से संपर्क करें**\n\n"
        "अगर आपको कोई प्रमोशन करना है या बॉट में कोई समस्या आ रही है, तो कृपया ओनर से संपर्क करें।\n\n"
        "➔ **ओनर:** @asbhaibsr"
    )
]

async def schedule_delete(message, delay_seconds=300):
    """Deletes the message after a specified delay."""
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Error deleting message: {e}")

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [
            [
                InlineKeyboardButton('🤖 Updates', url='https://t.me/asbhai_bsr')
            ],
            [
                InlineKeyboardButton('ℹ️ Help', url=f"https://t.me/{temp.U_NAME}?start=help"),
            ]
            ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(script.START_TXT.format(message.from_user.mention if message.from_user else message.chat.title, temp.U_NAME, temp.B_NAME), reply_markup=reply_markup)
        await asyncio.sleep(2)
        if not await db.get_chat(message.chat.id):
            total=await client.get_chat_members_count(message.chat.id)
            await client.send_message(LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))       
            await db.add_chat(message.chat.id, message.chat.title)
        return 
    
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))
        
    if len(message.command) != 2:
        buttons = [[
            InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ],[
            InlineKeyboardButton('ℹ️ ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')
        ],[
            InlineKeyboardButton('🤖 ᴏᴛʜᴇʀ ʙᴏᴛs & ᴄᴏɴᴛᴀᴄᴛ 🤖', callback_data='other_bots_0')
        ],[
            InlineKeyboardButton('📝 ʀᴇǫᴜᴇsᴛ ᴍᴏᴠɪᴇ/sᴇʀɪᴇs', callback_data='request_movie')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return
        
    if AUTH_CHANNEL and not await is_subscribed(client, message):
        try:
            auth_channel_id = int(AUTH_CHANNEL)
            invite_link = await client.create_chat_invite_link(auth_channel_id)
        except (ChatAdminRequired, PeerIdInvalid, ChannelInvalid, ValueError) as e:
            logger.error(f"Force-sub setup error for AUTH_CHANNEL {AUTH_CHANNEL}: {e}")
            await message.reply_text(
                "⚠️ **Force-Subscription Setup Error**\n\nPlease ensure the `AUTH_CHANNEL` ID is correct (e.g., `-100...`) and that the bot is an **administrator** in that channel with **Invite Link** permission."
            )
            return

        btn = [
            [
                InlineKeyboardButton(
                    "🤖 Join Updates Channel", url=invite_link.invite_link
                )
            ]
        ]

        if message.command[1] != "subscribe":
            try:
                kk, file_id = message.command[1].split("_", 1)
                pre = 'checksubp' if kk == 'filep' else 'checksub' 
                btn.append([InlineKeyboardButton(" 🔄 Try Again", callback_data=f"{pre}#{file_id}")])
            except (IndexError, ValueError):
                btn.append([InlineKeyboardButton(" 🔄 Try Again", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")])
        await client.send_message(
            chat_id=message.from_user.id,
            text="**Please Join My Updates Channel to use this Bot!**",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.MARKDOWN
            )
        return
        
    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help"]:
        buttons = [[
            InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ],[
            InlineKeyboardButton('ℹ️ ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')
        ],[
            InlineKeyboardButton('🤖 ᴏᴛʜᴇʀ ʙᴏᴛs & ᴄᴏɴᴛᴀᴄᴛ 🤖', callback_data='other_bots_0')
        ],[
            InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇs', url='https://t.me/asbhai_bsr')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return
        
    data = message.command[1]
    try:
        pre, file_id = data.split('_', 1)
    except:
        file_id = data
        pre = ""
    if data.split("-", 1)[0] == "BATCH":
        sts = await message.reply("Please wait")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            file = await client.download_media(file_id)
            try: 
                with open(file) as file_data:
                    msgs=json.loads(file_data.read())
            except:
                await sts.edit("FAILED")
                return await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
            os.remove(file)
            BATCH_FILES[file_id] = msgs
        for msg in msgs:
            title = msg.get("title")
            size=get_size(int(msg.get("size", 0)))
            f_caption=msg.get("caption", "")
            if BATCH_FILE_CAPTION:
                try:
                    f_caption=BATCH_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                except Exception as e:
                    logger.exception(e)
                    f_caption=f_caption
            if f_caption is None:
                f_caption = f"{title}"
            try:
                sent_msg = await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    protect_content=msg.get('protect', False),
                )
                asyncio.create_task(schedule_delete(sent_msg, 300))
            except FloodWait as e:
                await asyncio.sleep(e.x)
                logger.warning(f"Floodwait of {e.x} sec.")
                sent_msg = await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    protect_content=msg.get('protect', False),
                )
                asyncio.create_task(schedule_delete(sent_msg, 300))
            except Exception as e:
                logger.warning(e, exc_info=True)
                continue
            await asyncio.sleep(1) 
        await sts.delete()
        return
    elif data.split("-", 1)[0] == "DSTORE":
        sts = await message.reply("Please wait")
        b_string = data.split("-", 1)[1]
        decoded = (base64.urlsafe_b64decode(b_string + "=" * (-len(b_string) % 4))).decode("ascii")
        try:
            f_msg_id, l_msg_id, f_chat_id, protect = decoded.split("_", 3)
        except:
            f_msg_id, l_msg_id, f_chat_id = decoded.split("_", 2)
            protect = "/pbatch" if PROTECT_CONTENT else "batch"
        diff = int(l_msg_id) - int(f_msg_id)
        async for msg in client.iter_messages(int(f_chat_id), int(l_msg_id), int(f_msg_id)):
            if msg.media:
                media = getattr(msg, msg.media.value)
                if BATCH_FILE_CAPTION:
                    try:
                        f_caption=BATCH_FILE_CAPTION.format(file_name=getattr(media, 'file_name', ''), file_size=getattr(media, 'file_size', ''), file_caption=getattr(msg, 'caption', ''))
                    except Exception as e:
                        logger.exception(e)
                        f_caption = getattr(msg, 'caption', '')
                else:
                    media = getattr(msg, msg.media.value)
                    file_name = getattr(media, 'file_name', '')
                    f_caption = getattr(msg, 'caption', file_name)
                try:
                    sent_msg = await msg.copy(message.chat.id, caption=f_caption, protect_content=True if protect == "/pbatch" else False)
                    asyncio.create_task(schedule_delete(sent_msg, 300))
                except FloodWait as e:
                    await asyncio.sleep(e.x)
                    sent_msg = await msg.copy(message.chat.id, caption=f_caption, protect_content=True if protect == "/pbatch" else False)
                    asyncio.create_task(schedule_delete(sent_msg, 300))
                except Exception as e:
                    logger.exception(e)
                    continue
            elif msg.empty:
                continue
            else:
                try:
                    sent_msg = await msg.copy(message.chat.id, protect_content=True if protect == "/pbatch" else False)
                    asyncio.create_task(schedule_delete(sent_msg, 300))
                except FloodWait as e:
                    await asyncio.sleep(e.x)
                    sent_msg = await msg.copy(message.chat.id, protect_content=True if protect == "/pbatch" else False)
                    asyncio.create_task(schedule_delete(sent_msg, 300))
                except Exception as e:
                    logger.exception(e)
                    continue
            await asyncio.sleep(1) 
        return await sts.delete()
        
    files_ = await get_file_details(file_id)           
    if not files_:
        pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
        try:
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                protect_content=True if pre == 'filep' else False,
            )
            asyncio.create_task(schedule_delete(msg, 300))
            filetype = msg.media
            file = getattr(msg, filetype.value)
            title = file.file_name
            size=get_size(file.file_size)
            f_caption = f"<code>{title}</code>"
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption=CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='')
                except:
                    return
            await msg.edit_caption(f_caption)
            return
        except:
            pass
        return await message.reply('No such file exist.')
    files = files_[0]
    title = files.file_name
    size=get_size(files.file_size)
    f_caption=files.caption
    if CUSTOM_FILE_CAPTION:
        try:
            f_caption=CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
        except Exception as e:
            logger.exception(e)
            f_caption=f_caption
    if f_caption is None:
        f_caption = f"{files.file_name}"
    
    # Send the file with caption
    sent_msg = await client.send_cached_media(
        chat_id=message.from_user.id,
        file_id=file_id,
        caption=f_caption,
        protect_content=True if pre == 'filep' else False,
    )
    
    # Send warning message separately
    warning_text = """
Hello,

⚠️ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ 5 ᴍɪɴᴜᴛᴇs

ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇ sᴏᴍᴇᴡʜᴇʀᴇ ʙᴇғᴏʀᴇ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ..

मूवी यहां डाउनलोड ना करे क्योंकि | मूवी 🍿 5 Minutes में डिलीट कर दी जायेगी
कृपया कही फॉरवर्ड करे के डाउनलोड करे
"""
    warn_msg = await client.send_message(
        chat_id=message.from_user.id,
        text=warning_text,
        reply_to_message_id=sent_msg.id
    )
    
    # Schedule deletion of both messages
    asyncio.create_task(schedule_delete(sent_msg, 300))
    asyncio.create_task(schedule_delete(warn_msg, 300))

@Client.on_callback_query(filters.regex(r"^other_bots_"))
async def other_bots_callback(client, query):
    try:
        page_index = int(query.data.split("_")[2])
    except IndexError:
        return

    buttons = []
    nav_buttons = []
    if page_index > 0:
        nav_buttons.append(InlineKeyboardButton(f"⬅️ ᴘɪᴄʜʟᴀ", callback_data=f"other_bots_{page_index-1}"))
    
    if page_index < len(BOTS_PAGES) - 1:
        nav_buttons.append(InlineKeyboardButton(f"ᴀɢʟᴀ ➡️", callback_data=f"other_bots_{page_index+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton("🔙 ᴠᴀᴘᴀs", callback_data="start_back")])

    reply_markup = InlineKeyboardMarkup(buttons)

    try:
        await query.message.edit_caption(
            caption=BOTS_PAGES[page_index],
            reply_markup=reply_markup
        )
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Could not edit message for other_bots: {e}")

@Client.on_callback_query(filters.regex("start_back"))
async def start_back_callback(client, query):
    buttons = [[
        InlineKeyboardButton('➕ ᴀᴅᴇᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
    ],[
        InlineKeyboardButton('ℹ️ ʜᴇʟᴘ', callback_data='help'),
        InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')
    ],[
        InlineKeyboardButton('🤖 ᴏᴛʜᴇʀ ʙᴏᴛs & ᴄᴏɴᴛᴀᴄᴛ 🤖', callback_data='other_bots_0')
    ],[
        InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇs', url='https://t.me/asbhai_bsr')
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    try:
        await query.message.edit_caption(
            caption=script.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in start_back_callback: {e}")

# ---------------- REQUEST MOVIE SYSTEM START ----------------

@Client.on_callback_query(filters.regex("request_movie"))
async def request_movie_click(client, query):
    await query.answer()
    await client.send_message(
        chat_id=query.from_user.id,
        text="👋 **Hello " + query.from_user.first_name + "!**\n\n"
             "Apni Movie/Series ka naam Language aur Year ke sath niche likh kar bhejein.\n\n"
             "Example: `Pushpa 2 Hindi 2024`",
        reply_markup=ForceReply(selective=True)
    )

@Client.on_message(filters.private & filters.reply)
async def handle_request_reply(client, message):
    if message.reply_to_message and "Apni Movie/Series ka naam" in message.reply_to_message.text:
        
        request_text = message.text
        user_id = message.from_user.id
        user_mention = message.from_user.mention
        
        await message.reply_text("✅ **Aapki Request Owner ko bhej di gayi hai!**\nJald hi upload kar di jayegi.")
        
        admin_buttons = [
            [
                InlineKeyboardButton("✅ Uploaded", callback_data=f"reqstatus#up#{user_id}"),
                InlineKeyboardButton("❌ Rejected", callback_data=f"reqstatus#rej#{user_id}")
            ],
            [
                InlineKeyboardButton("⚠️ Not Released", callback_data=f"reqstatus#nore#{user_id}")
            ]
        ]
        
        notification_text = (
            f"🔔 **New Movie Request!**\n\n"
            f"👤 **User:** {user_mention} (`{user_id}`)\n"
            f"🎬 **Request:** `{request_text}`"
        )
        
        for admin_id in ADMINS:
            try:
                await client.send_message(
                    chat_id=int(admin_id),
                    text=notification_text,
                    reply_markup=InlineKeyboardMarkup(admin_buttons)
                )
            except Exception as e:
                logger.error(f"Failed to send request to admin {admin_id}: {e}")

@Client.on_callback_query(filters.regex(r"^reqstatus"))
async def handle_request_status(client, query):
    data = query.data.split("#")
    action = data[1]
    user_id = int(data[2])
    
    movie_name = "Unknown"
    try:
        movie_name = query.message.text.split("Request:** `")[1].split("`")[0]
    except:
        pass

    if action == "up":
        text_for_user = f"✅ **Request Completed!**\n\nApki movie **{movie_name}** upload kar di gayi hai. Ab aap bot par search kar sakte hain."
        text_for_admin = f"✅ Request marked as **Uploaded** for {movie_name}."
        
    elif action == "rej":
        text_for_user = f"❌ **Request Rejected!**\n\nApki request **{movie_name}** reject kar di gayi hai. (Possible reasons: Spam, Incorrect name, or Unavailable)."
        text_for_admin = f"❌ Request marked as **Rejected** for {movie_name}."
        
    elif action == "nore":
        text_for_user = f"⚠️ **Not Released Yet!**\n\nSorry, **{movie_name}** abhi release nahi hui hai ya High Quality mein available nahi hai."
        text_for_admin = f"⚠️ Request marked as **Not Released** for {movie_name}."

    try:
        await client.send_message(chat_id=user_id, text=text_for_user)
    except Exception as e:
        await query.answer("User ne bot block kiya hai ya message nahi ja raha.", show_alert=True)
        return

    await query.message.edit_text(
        text=query.message.text + f"\n\n➖➖➖➖➖➖➖\n{text_for_admin}",
        reply_markup=None
    )
    await query.answer("User notified!")

# ---------------- GROUP REQUEST SYSTEM START ----------------

@Client.on_message(filters.command("request", prefixes=["/", "#"]) & filters.group)
async def group_movie_request(client, message):
    if len(message.command) < 2:
        return await message.reply_text("⚠️ **उपयोग:** `/request Movie Name`\nExample: `/request Pushpa 2`")
    
    movie_name = message.text.split(" ", 1)[1]
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    group_title = message.chat.title
    group_id = message.chat.id
    message_link = message.link 
    
    reply_text = (
        f"👋 हेलो {user_mention}!\n\n"
        f"📝 **आपकी रिक्वेस्ट:** `{movie_name}`\n\n"
        f"✅ **स्टेटस:** आपकी रिक्वेस्ट ओनर (Owner) के पास भेज दी गई है।\n"
        f"⏳ कृपया थोड़ा इंतज़ार करें, एडमिन अपने काम में व्यस्त हो सकते हैं।\n"
        f"🔔 जैसे ही मूवी अपलोड होगी या रिजेक्ट होगी, आपको यहीं नोटिफिकेशन मिल जाएगा।"
    )
    await message.reply_text(reply_text)

    admin_text = (
        f"📩 **New Group Request**\n\n"
        f"👤 **User:** {user_mention} (`{user_id}`)\n"
        f"🏘 **Group:** {group_title} (`{group_id}`)\n"
        f"🔗 **Message Link:** [Click Here]({message_link})\n"
        f"🎬 **Movie:** `{movie_name}`"
    )

    buttons = [
        [
            InlineKeyboardButton("✅ Uploaded", callback_data=f"greq#up#{user_id}#{group_id}"),
            InlineKeyboardButton("❌ Rejected", callback_data=f"greq#rej#{user_id}#{group_id}")
        ],
        [
            InlineKeyboardButton("⚠️ Not Released", callback_data=f"greq#nore#{user_id}#{group_id}")
        ]
    ]

    await client.send_message(
        chat_id=REQUEST_CHANNEL,
        text=admin_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex(r"^greq"))
async def handle_group_request_status(client, query):
    _, action, user_id, group_id = query.data.split("#")
    user_id = int(user_id)
    group_id = int(group_id)
    
    try:
        movie_name = query.message.text.split("Movie:** `")[1].split("`")[0]
    except:
        movie_name = "Movie"

    if action == "up":
        status_msg = f"✅ **Request Completed!**\n\nMovie: `{movie_name}`\nस्टेटस: अपलोड कर दी गई है! बॉट पर सर्च करें।"
        admin_log = f"✅ Request Uploaded: {movie_name}"
    elif action == "rej":
        status_msg = f"❌ **Request Rejected!**\n\nMovie: `{movie_name}`\nस्टेटस: रिजेक्ट कर दी गई है (Unavailable/Spam)."
        admin_log = f"❌ Request Rejected: {movie_name}"
    elif action == "nore":
        status_msg = f"⚠️ **Not Released!**\n\nMovie: `{movie_name}`\nस्टेटस: अभी रिलीज़ नहीं हुई है या HD में नहीं है।"
        admin_log = f"⚠️ Request Not Released: {movie_name}"

    try:
        await client.send_message(
            chat_id=group_id,
            text=f"<a href='tg://user?id={user_id}'>👤</a> {status_msg}"
        )
        await query.answer("User Notified in Group!")
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)

    await query.message.edit_text(
        query.message.text + f"\n\n➖➖➖➖➖\n{admin_log}",
        reply_markup=None
    )

# ---------------- GROUP REQUEST SYSTEM END ----------------

@Client.on_message(
    filters.private & 
    filters.text & 
    filters.incoming & 
    ~filters.user(ADMINS) & 
    ~filters.command(["start", "help", "settings", "id", "status", "batch", "connect", "disconnect", "stats", "set_template"])
)
async def pm_text_search_handler(client, message):
    buttons = [[
        InlineKeyboardButton('🎬 Free Movie Search Group 🍿', url='https://t.me/freemoviesearchgroup')
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    text = (
        "**❌ आप यहाँ (PM) में मूवी सर्च नहीं कर सकते।**\n\n"
        "कृपया हमारे **फ्री मूवी सर्च ग्रुप** को जॉइन करें और वहाँ मूवी सर्च करें। 👇\n\n"
        "--- \n\n"
        "**❌ You cannot search for movies here (in PM).**\n\n"
        "Please join our **Free Movie Search Group** and search for movies there. 👇"
    )
    
    await message.reply_text(
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.MARKDOWN
    )
                    
@Client.on_message(filters.command('channel') & filters.user(ADMINS))
async def channel_info(bot, message):
    if isinstance(CHANNELS, (int, str)):
        channels = [CHANNELS]
    elif isinstance(CHANNELS, list):
        channels = CHANNELS
    else:
        raise ValueError("Unexpected type of CHANNELS")

    text = '📑 **Indexed channels/groups**\n'
    for channel in channels:
        try:
            chat = await bot.get_chat(channel)
            if chat.username:
                text += '\n@' + chat.username
            else:
                text += '\n' + chat.title or chat.first_name
        except Exception as e:
            logger.error(f"Error getting chat info for channel {channel}: {e}")
            text += f'\n(Error getting info for {channel})'

    text += f'\n\n**Total:** {len(CHANNELS)}'

    if len(text) < 4096:
        await message.reply(text)
    else:
        file = 'Indexed channels.txt'
        with open(file, 'w') as f:
            f.write(text)
        await message.reply_document(file)
        os.remove(file)

@Client.on_message(filters.command('logs') & filters.user(ADMINS))
async def log_file(bot, message):
    try:
        await message.reply_document('TelegramBot.log')
    except Exception as e:
        await message.reply(str(e))

@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete(bot, message):
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("Processing...⏳", quote=True)
    else:
        await message.reply('Reply to file with /delete which you want to delete', quote=True)
        return

    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    else:
        await msg.edit('This is not supported file format')
        return
    
    file_id, file_ref = unpack_new_file_id(media.file_id)

    result = await Media.collection.delete_one({
        '_id': file_id,
    })
    if result.deleted_count:
        await msg.edit('File is successfully deleted from database')
    else:
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
        result = await Media.collection.delete_many({
            'file_name': file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
            })
        if result.deleted_count:
            await msg.edit('File is successfully deleted from database')
        else:
            result = await Media.collection.delete_many({
                'file_name': media.file_name,
                'file_size': media.file_size,
                'mime_type': media.mime_type
            })
            if result.deleted_count:
                await msg.edit('File is successfully deleted from database')
            else:
                await msg.edit('File not found in database')

@Client.on_message(filters.command('deleteall') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'This will delete all indexed files.\nDo you want to continue??',
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="YES", callback_data="autofilter_delete"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="CANCEL", callback_data="close_data"
                    )
                ],
            ]
        ),
        quote=True,
    )

@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, message):
    await Media.collection.drop()
    await message.answer('Piracy Is Crime')
    await message.message.edit('Succesfully Deleted All The Indexed Files.')

@Client.on_message(filters.command('settings'))
async def settings(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
            st.status != enums.ChatMemberStatus.ADMINISTRATOR
            and st.status != enums.ChatMemberStatus.OWNER
            and str(userid) not in ADMINS
    ):
        return

    settings = await get_settings(grp_id)

    if settings is not None:
        buttons = [
            [
                InlineKeyboardButton(
                    'Filter Button',
                    callback_data=f'setgs#button#{settings["button"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    'Single' if settings["button"] else 'Double',
                    callback_data=f'setgs#button#{settings["button"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    'Bot PM',
                    callback_data=f'setgs#botpm#{settings["botpm"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ Yes' if settings["botpm"] else '❌ No',
                    callback_data=f'setgs#botpm#{settings["botpm"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    'File Secure',
                    callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ Yes' if settings["file_secure"] else '❌ No',
                    callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    'IMDB',
                    callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ Yes' if settings["imdb"] else '❌ No',
                    callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    'Spell Check',
                    callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ Yes' if settings["spell_check"] else '❌ No',
                    callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    'Welcome',
                    callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ Yes' if settings["welcome"] else '❌ No',
                    callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}',
                ),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(buttons)

        await message.reply_text(
            text=f"<b>Change Your Settings for {title} As Your Wish ⚙</b>",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=message.id
        )

@Client.on_message(filters.command('set_template'))
async def save_template(client, message):
    sts = await message.reply("Checking template")
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
            st.status != enums.ChatMemberStatus.ADMINISTRATOR
            and st.status != enums.ChatMemberStatus.OWNER
            and str(userid) not in ADMINS
    ):
        return

    if len(message.command) < 2:
        return await sts.edit("No Input!!")
    template = message.text.split(" ", 1)[1]
    await save_group_settings(grp_id, 'template', template)
    await sts.edit(f"Successfully changed template for {title} to\n\n{template}")
