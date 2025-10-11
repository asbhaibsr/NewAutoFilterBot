import asyncio
import re
import ast
import math
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from database.connections_mdb import active_connection, all_connections, delete_connection, if_active, make_active, make_inactive
from info import ADMINS, AUTH_CHANNEL, AUTH_USERS, CUSTOM_FILE_CAPTION, AUTH_GROUPS, P_TTI_SHOW_OFF, IMDB, SINGLE_BUTTON, SPELL_CHECK_REPLY, IMDB_TEMPLATE
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import get_size, is_subscribed, get_poster, search_gagala, temp, get_settings, save_group_settings
from database.users_chats_db import db
from database.ia_filterdb import Media, get_file_details, get_search_results
from database.filters_mdb import del_all, find_filter, get_filters
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}

# Enhanced fancy font converter
def to_fancy_font(text):
    """Converts text to fancy font style"""
    mapping = {
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ', 'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 
        'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 
        'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ',
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ',
        'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ',
        'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        '0': '𝟶', '1': '𝟷', '2': '𝟸', '3': '𝟹', '4': '𝟺', '5': '𝟻', '6': '𝟼', '7': '𝟽', '8': '𝟾', '9': '𝟿',
        ' ': ' ', '.': '.', ',': ',', '!': '!', '?': '?', '-': '-', '_': '_', '/': '/', '\\': '\\',
        '(': '(', ')': ')', '[': '[', ']': ']', '{': '{', '}': '}'
    }
    return ''.join(mapping.get(char, char) for char in text)

async def schedule_delete(message, delay_seconds):
    """Delete message after specified delay"""
    await asyncio.sleep(delay_seconds)
    try:
        # Check if the message object and its id are valid
        if message and hasattr(message, 'id') and message.id:
            await message.delete()
    except Exception as e:
        logger.warning(f"Error deleting message: {e}")

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    k = await manual_filters(client, message)
    if k == False:
        await auto_filter(client, message)

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer("oKda", show_alert=True)
        
    # FIX 1: Ensure offset is an integer before use
    try:
        offset = int(offset)
    except ValueError:
        offset = 0  # Default to 0 if offset is not a valid integer (e.g., empty string)
    
    search = BUTTONS.get(key)
    if not search:
        await query.answer("You are using one of my old messages, please send the request again.", show_alert=True)
        return

    files, n_offset, total = await get_search_results(search, offset=offset, filter=True)
    try:
        # FIX 1.1: Ensure n_offset is an integer before comparison/use
        n_offset = int(n_offset) if n_offset else 0
    except ValueError:
        n_offset = 0

    if not files:
        # If no files found for the next page, just answer and return
        await query.answer("No more results.", show_alert=True)
        return

    settings = await get_settings(query.message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    
    # File buttons
    if settings['button']:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"📁 {to_fancy_font(file.file_name)}",
                    callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"📂 {to_fancy_font(file.file_name)}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
                InlineKeyboardButton(
                    text=f"💾 {to_fancy_font(get_size(file.file_size))}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
            ]
            for file in files
        ]

    # Filter buttons row
    btn.append([
        InlineKeyboardButton(text="🎬 Qᴜᴀʟɪᴛʏ", callback_data="quality_dummy"),
        InlineKeyboardButton(text="🌐 Lᴀɴɢᴜᴀɢᴇ", callback_data="language_dummy"),
        InlineKeyboardButton(text="📺 Sᴇᴀsᴏɴ", callback_data="season_dummy")
    ])
    
    # Chennai Express specific session buttons
    chennai_sessions = []
    for i in range(1, 51):
        session_num = f"{i:02d}"
        chennai_sessions.append(
            InlineKeyboardButton(
                text=f"S{session_num}", 
                callback_data=f"session_{session_num}"
            )
        )
    
    # Add session buttons in rows of 5
    for i in range(0, len(chennai_sessions), 5):
        btn.append(chennai_sessions[i:i+5])
    
    # Indian language buttons
    indian_languages = [
        ("Hindi", "lang_hindi"),
        ("Tamil", "lang_tamil"), 
        ("Telugu", "lang_telugu"),
        ("Malayalam", "lang_malayalam"),
        ("Kannada", "lang_kannada"),
        ("Bengali", "lang_bengali"),
        ("Marathi", "lang_marathi"),
        ("Gujarati", "lang_gujarati"),
        ("Punjabi", "lang_punjabi")
    ]
    
    lang_buttons = []
    for lang_name, lang_data in indian_languages:
        lang_buttons.append(
            InlineKeyboardButton(
                text=to_fancy_font(lang_name),
                callback_data=lang_data
            )
        )
    
    # Add language buttons in rows of 3
    for i in range(0, len(lang_buttons), 3):
        btn.append(lang_buttons[i:i+3])
    
    # Send All Files button
    btn.append([
        InlineKeyboardButton(
            text="🚀 Sᴇɴᴅ Aʟʟ Fɪʟᴇs", 
            callback_data=f"sendall_{key}"
        )
    ])
    
    # Check Bot PM button
    btn.append([
        InlineKeyboardButton(
            text="🔍 Cʜᴇᴄᴋ Bᴏᴛ PM", 
            url=f"https://t.me/{temp.U_NAME}"
        )
    ])

    # Pagination
    current_page = math.ceil(offset / 10) + 1
    total_pages = math.ceil(total / 10)
    
    pagination_buttons = []
    if offset > 0:
        pagination_buttons.append(
            InlineKeyboardButton("⏪ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset-10}")
        )
    
    pagination_buttons.append(
        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages")
    )
    
    if n_offset != 0:
        pagination_buttons.append(
            InlineKeyboardButton("Nᴇxᴛ ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
        )
    
    if pagination_buttons:
        btn.append(pagination_buttons)

    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    await query.answer()

@Client.on_callback_query(filters.regex(r"^sendall"))
async def send_all_files(bot, query):
    """Send all files to PM at once"""
    _, key = query.data.split("_")
    
    search = BUTTONS.get(key)
    if not search:
        await query.answer("Search expired. Please search again.", show_alert=True)
        return
    
    await query.answer("Sending all files to your PM...", show_alert=True)
    
    # Get all files for this search
    all_files = []
    offset = 0
    while True:
        # NOTE: max_results should ideally be a constant, using 100 for now.
        files, next_offset, total = await get_search_results(search, offset=offset, max_results=100, filter=True)
        all_files.extend(files)
        
        # Ensure next_offset is converted to int or defaults to 0
        try:
            next_offset = int(next_offset)
        except (TypeError, ValueError):
            next_offset = 0

        if next_offset == 0:
            break
        offset = next_offset
    
    if not all_files:
        await query.message.reply_text("❌ No files found to send.")
        return
    
    user_id = query.from_user.id
    sent_count = 0
    
    # Send files to user's PM
    for file in all_files:
        try:
            file_caption = file.caption or f"{file.file_name}"
            if CUSTOM_FILE_CAPTION:
                try:
                    file_caption = CUSTOM_FILE_CAPTION.format(
                        file_name=file.file_name,
                        file_size=get_size(file.file_size),
                        file_caption=file.caption or ""
                    )
                except Exception as e:
                    logger.exception(e)
            
            # Send file to user's PM
            sent_msg = await bot.send_cached_media(
                chat_id=user_id,
                file_id=file.file_id,
                caption=file_caption,
                protect_content=True
            )
            
            sent_count += 1
            
            # Schedule deletion after 5 minutes
            asyncio.create_task(schedule_delete(sent_msg, 300))
            
            # Small delay to avoid flooding
            await asyncio.sleep(0.5)
            
        except UserIsBlocked:
            await query.message.reply_text("❌ Please unblock the bot first!")
            return
        except Exception as e:
            logger.error(f"Error sending file {file.file_name}: {e}")
            continue
    
    # Notification
    notification = await query.message.reply_text(
        f"✅ Successfully sent {sent_count} files to your PM!\n"
        f"📁 Files will be auto-deleted in 5 minutes.\n"
        f"🔍 Search: `{search}`"
    )
    
    # Delete notification after 10 seconds
    asyncio.create_task(schedule_delete(notification, 10))

@Client.on_callback_query(filters.regex(r"^session_"))
async def handle_session(bot, query):
    """Handle session button clicks"""
    session_num = query.data.split("_")[1]
    await query.answer(f"Selected Session {session_num}", show_alert=False)

@Client.on_callback_query(filters.regex(r"^lang_"))
async def handle_language(bot, query):
    """Handle language button clicks"""
    lang_code = query.data.split("_")[1]
    lang_names = {
        "hindi": "Hindi", "tamil": "Tamil", "telugu": "Telugu",
        "malayalam": "Malayalam", "kannada": "Kannada", "bengali": "Bengali",
        "marathi": "Marathi", "gujarati": "Gujarati", "punjabi": "Punjabi"
    }
    lang_name = lang_names.get(lang_code, "Unknown")
    await query.answer(f"Selected {lang_name} language", show_alert=False)

@Client.on_callback_query(filters.regex(r"^(quality|language|season)_dummy$"))
async def handle_dummy_buttons(bot, query):
    """Handle dummy filter buttons"""
    await query.answer()

@Client.on_callback_query(filters.regex(r"^spolling"))
async def advantage_spoll_choker(bot, query):
    _, user, movie_ = query.data.split('#')
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer("oKda", show_alert=True)
    if movie_ == "close_spellcheck":
        return await query.message.delete()
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer("You are clicking on an old button which is expired.", show_alert=True)
    movie = movies[(int(movie_))]
    await query.answer('Checking for Movie in database...')
    # Pass query message, not the callback query object
    k = await manual_filters(bot, query.message.reply_to_message, text=movie)
    if k == False:
        files, offset, total_results = await get_search_results(movie, offset=0, filter=True)
        if files:
            k = (movie, files, offset, total_results)
            await auto_filter(bot, query, k)
        else:
            k = await query.message.edit('This Movie Not Found In DataBase')
            asyncio.create_task(schedule_delete(k, 10))

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await query.message.delete()
    
    elif query.data in ["quality_dummy", "language_dummy", "season_dummy"]:
        await query.answer()
    
    elif query.data.startswith("sendall"):
        # This will be handled by the send_all_files function above
        pass
    
    elif query.data.startswith("session_"):
        # This will be handled by the handle_session function above  
        pass
    
    elif query.data.startswith("lang_"):
        # This will be handled by the handle_language function above
        pass
    
    elif query.data == "delallconfirm":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            grpid = await active_connection(str(userid))
            if grpid is not None:
                grp_id = grpid
                try:
                    chat = await client.get_chat(grpid)
                    title = chat.title
                except:
                    await query.message.edit_text("Make sure I'm present in your group!!", quote=True)
                    return await query.answer('Piracy Is Crime')
            else:
                await query.message.edit_text(
                    "I'm not connected to any groups!\nCheck /connections or connect to any groups",
                    quote=True
                )
                return await query.answer('Piracy Is Crime')

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            title = query.message.chat.title

        else:
            return await query.answer('Piracy Is Crime')

        st = await client.get_chat_member(grp_id, userid)
        if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
            await del_all(query.message, grp_id, title)
        else:
            await query.answer("You need to be Group Owner or an Auth User to do that!", show_alert=True)
    elif query.data == "delallcancel":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            # Safely attempt to delete the reply_to_message and the current message
            try:
                if query.message.reply_to_message:
                    await query.message.reply_to_message.delete()
            except:
                pass
            await query.message.delete()

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            st = await client.get_chat_member(grp_id, userid)
            if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
                await query.message.delete()
                try:
                    await query.message.reply_to_message.delete()
                except:
                    pass
            else:
                await query.answer("That's not for you!!", show_alert=True)
    elif "groupcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        act = query.data.split(":")[2]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id

        if act == "":
            stat = "ᴄᴏɴɴᴇᴄᴛ"
            cb = "connectcb"
        else:
            stat = "ᴅɪsᴄᴏɴɴᴇᴄᴛ"
            cb = "disconnect"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{stat}", callback_data=f"{cb}:{group_id}"),
             InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ", callback_data=f"deletecb:{group_id}")],
            [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="backcb")]
        ])

        await query.message.edit_text(
            f"Gʀᴏᴜᴘ Nᴀᴍᴇ : **{title}**\nGʀᴏᴜᴘ Iᴅ : `{group_id}`",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return await query.answer('Piracy Is Crime')
    elif "connectcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title

        user_id = query.from_user.id

        mkact = await make_active(str(user_id), str(group_id))

        if mkact:
            await query.message.edit_text(
                f"ᴄᴏɴɴᴇᴄᴛᴇᴅ ᴛᴏ **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text('Sᴏᴍᴇ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!!', parse_mode=enums.ParseMode.MARKDOWN)
        return await query.answer('Piracy Is Crime')
    elif "disconnect" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title
        user_id = query.from_user.id

        mkinact = await make_inactive(str(user_id))

        if mkinact:
            await query.message.edit_text(
                f"ᴅɪsᴄᴏɴɴᴇᴄᴛᴇᴅ ғʀᴏᴍ **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text(
                f"Sᴏᴍᴇ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer('Piracy Is Crime')
    elif "deletecb" in query.data:
        await query.answer()

        user_id = query.from_user.id
        group_id = query.data.split(":")[1]

        delcon = await delete_connection(str(user_id), str(group_id))

        if delcon:
            await query.message.edit_text(
                "Sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ᴄᴏɴɴᴇᴄᴛɪᴏɴ"
            )
        else:
            await query.message.edit_text(
                f"Sᴏᴍᴇ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer('Piracy Is Crime')
    elif query.data == "backcb":
        await query.answer()

        userid = query.from_user.id

        groupids = await all_connections(str(userid))
        if groupids is None:
            await query.message.edit_text(
                "Tʜᴇʀᴇ ᴀʀᴇ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴄᴏɴɴᴇᴄᴛɪᴏɴs!! ᴄᴏɴɴᴇᴄᴛ ᴛᴏ sᴏᴍᴇ ɢʀᴏᴜᴘs ғɪʀsᴛ.",
            )
            return await query.answer('Piracy Is Crime')
        buttons = []
        for groupid in groupids:
            try:
                ttl = await client.get_chat(int(groupid))
                title = ttl.title
                active = await if_active(str(userid), str(groupid))
                act = " - ᴀᴄᴛɪᴠᴇ" if active else ""
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                        )
                    ]
                )
            except:
                pass
        if buttons:
            await query.message.edit_text(
                "Yᴏᴜʀ ᴄᴏɴɴᴇᴄᴛᴇᴅ ɢʀᴏᴜᴘ ᴅᴇᴛᴀɪʟs ;\n\n",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    elif "alertmessage" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_filter(grp_id, keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)
    
    # PM ISSUE FIX & File Sent Message Logic
    if query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('Nᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
        
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        settings = await get_settings(query.message.chat.id)
        
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files.file_name}"

        # 1. Force Sub/Bot PM Check
        if (AUTH_CHANNEL and not await is_subscribed(client, query)) or settings['botpm']:
            # Force user to PM the bot to get the file/check sub
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
            return
        
        # 2. Try sending the file to PM (The main fix for PM issue)
        try:
            sent_msg = await client.send_cached_media(
                chat_id=query.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=True if ident == "filep" else False 
            )
            
            # Warning message
            warning_message = f"""
**ʜᴇʟʟᴏ** {query.from_user.mention},

**⚠️ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ 5 ᴍɪɴᴜᴛᴇs**

**ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇ sᴏᴍᴇᴡʜᴇʀᴇ ʙᴇғᴏʀᴇ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ..**

**मूवी यहां डाउनलोड ना करे क्योंकि | मूवी 🍿 5 Minutes में डिलीट कर दी जायेगी**
**कृपया कही फॉरवर्ड करे के डाउनलोड करे**
"""
            
            # Sent the warning message after the file
            await sent_msg.reply_text(warning_message, quote=True)

            # Schedule file deletion in PM after 5 minutes (300 seconds)
            asyncio.create_task(schedule_delete(sent_msg, 300))
            
            # Answer the callback query
            await query.answer('ᴄʜᴇᴄᴋ ᴘᴍ, ɪ ʜᴀᴠᴇ sᴇɴᴛ ᴛʜᴇ ғɪʟᴇ. ɪᴛ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ 5 ᴍɪɴᴜᴛᴇs.', show_alert=True)
            
        except UserIsBlocked:
            await query.answer('ᴜɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ғɪʀsᴛ!', show_alert=True)
        except PeerIdInvalid:
            # This handles the case where the user hasn't started the bot yet.
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
        except Exception as e:
            # Catch all other errors and redirect to PM as a fallback
            logger.exception(f"Error sending file to PM: {e}")
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
            
    elif query.data.startswith("checksub"):
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer("ɪ ʟɪᴋᴇ ʏᴏᴜʀ sᴍᴀʀᴛɴᴇss, ʙᴜᴛ ᴅᴏɴ'ᴛ ʙᴇ ᴏᴠᴇʀsᴍᴀʀᴛ 😒", show_alert=True)
            return
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('ɴᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
                f_caption = f_caption
        if f_caption is None:
            f_caption = f"{title}"
        await query.answer()
        sent_msg = await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == 'checksubp' else False
        )
        # Schedule file deletion after 5 minutes
        asyncio.create_task(schedule_delete(sent_msg, 300))

    elif query.data == "pages":
        await query.answer()
    elif query.data == "start":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ➕'), url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ], [
            InlineKeyboardButton(to_fancy_font('🔍 sᴇᴀʀᴄʜ'), switch_inline_query_current_chat=''),
            InlineKeyboardButton(to_fancy_font('🤖 ᴜᴘᴅᴀᴛᴇs'), url='https://t.me/TechMagazineYT')
        ], [
            InlineKeyboardButton(to_fancy_font('ℹ️ ʜᴇʟᴘ'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('😊 ᴀʙᴏᴜᴛ'), callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer('Piracy Is Crime')
    elif query.data == "help":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('ᴍᴀɴᴜᴀʟ ғɪʟᴛᴇʀ'), callback_data='manuelfilter'),
            InlineKeyboardButton(to_fancy_font('ᴀᴜᴛᴏ ғɪʟᴛᴇʀ'), callback_data='autofilter')
        ], [
            InlineKeyboardButton(to_fancy_font('ᴄᴏɴɴᴇᴄᴛɪᴏɴ'), callback_data='coct'),
            InlineKeyboardButton(to_fancy_font('ᴇxᴛʀᴀ ᴍᴏᴅs'), callback_data='extra')
        ], [
            InlineKeyboardButton(to_fancy_font('🏠 ʜᴏᴍᴇ'), callback_data='start'),
            InlineKeyboardButton(to_fancy_font('🔮 sᴛᴀᴛᴜs'), callback_data='stats')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.HELP_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "about":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('🤖 ᴜᴘᴅᴀᴛᴇs'), url='https://t.me/TechMagazineYT'),
            InlineKeyboardButton(to_fancy_font('♥️ sᴏᴜʀᴄᴇ'), callback_data='source')
        ], [
            InlineKeyboardButton(to_fancy_font('🏠 ʜᴏᴍᴇ'), callback_data='start'),
            InlineKeyboardButton(to_fancy_font('🔐 ᴄʟᴏsᴇ'), callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "source":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 ʙᴀᴄᴋ'), callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.SOURCE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "manuelfilter":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 ʙᴀᴄᴋ'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('⏹️ ʙᴜᴛᴛᴏɴs'), callback_data='button')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.MANUELFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "button":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 ʙᴀᴄᴋ'), callback_data='manuelfilter')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.BUTTON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "autofilter":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 ʙᴀᴄᴋ'), callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.AUTOFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "coct":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 ʙᴀᴄᴋ'), callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CONNECTION_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "extra":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 ʙᴀᴄᴋ'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('👮‍♂️ ᴀᴅᴍɪɴ'), callback_data='admin')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.EXTRAMOD_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "admin":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 ʙᴀᴄᴋ'), callback_data='extra')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ADMIN_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "stats":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 ʙᴀᴄᴋ'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('♻️ ʀᴇғʀᴇsʜ'), callback_data='rfrsh')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        total = await Media.count_documents()
        users = await db.total_users_count()
        chats = await db.total_chat_count()
        monsize = await db.get_db_size()
        free = 536870912 - monsize
        monsize = get_size(monsize)
        free = get_size(free)
        await query.message.edit_text(
            text=script.STATUS_TXT.format(total, users, chats, monsize, free),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "rfrsh":
        await query.answer("ғᴇᴛᴄʜɪɴɢ ᴍᴏɴɢᴏᴅʙ ᴅᴀᴛᴀʙᴀsᴇ")
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 ʙᴀᴄᴋ'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('♻️ ʀᴇғʀᴇsʜ'), callback_data='rfrsh')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        total = await Media.count_documents()
        users = await db.total_users_count()
        chats = await db.total_chat_count()
        monsize = await db.get_db_size()
        free = 536870912 - monsize
        monsize = get_size(monsize)
        free = get_size(free)
        await query.message.edit_text(
            text=script.STATUS_TXT.format(total, users, chats, monsize, free),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data.startswith("setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        grpid = await active_connection(str(query.from_user.id))

        if str(grp_id) != str(grpid):
            await query.message.edit("Yᴏᴜʀ ᴀᴄᴛɪᴠᴇ ᴄᴏɴɴᴇᴄᴛɪᴏɴ ʜᴀs ʙᴇᴇɴ ᴄʜᴀɴɢᴇᴅ. ɢᴏ ᴛᴏ /sᴇᴛᴛɪɴɢs.")
            return await query.answer('Piracy Is Crime')

        # status is a string, convert to boolean for logical inversion
        current_status = True if status == "True" else False

        if current_status:
            await save_group_settings(grpid, set_type, False)
        else:
            await save_group_settings(grpid, set_type, True)

        settings = await get_settings(grpid)

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton(to_fancy_font('ғɪʟᴛᴇʀ ʙᴜᴛᴛᴏɴ'),
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('sɪɴɢʟᴇ') if settings["button"] else to_fancy_font('ᴅᴏᴜʙʟᴇ'),
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('ʙᴏᴛ ᴘᴍ'), callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ ʏᴇs') if settings["botpm"] else to_fancy_font('❌ ɴᴏ'),
                                         callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('ғɪʟᴇ sᴇᴄᴜʀᴇ'),
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ ʏᴇs') if settings["file_secure"] else to_fancy_font('❌ ɴᴏ'),
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('ɪᴍᴅʙ'), callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ ʏᴇs') if settings["imdb"] else to_fancy_font('❌ ɴᴏ'),
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('sᴘᴇʟʟ ᴄʜᴇᴄᴋ'),
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ ʏᴇs') if settings["spell_check"] else to_fancy_font('❌ ɴᴏ'),
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('ᴡᴇʟᴄᴏᴍᴇ'), callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ ʏᴇs') if settings["welcome"] else to_fancy_font('❌ ɴᴏ'),
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_reply_markup(reply_markup)
    await query.answer('Piracy Is Crime')

async def auto_filter(client, msg, spoll=False):
    if not spoll:
        message = msg
        settings = await get_settings(message.chat.id)
        if message.text.startswith("/"): return
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if 2 < len(message.text) < 100:
            search = message.text
            searching = await message.reply_sticker("CAACAgUAAxkBAAEEZo1o6SlcFV3q8zLbRtOOyNAVornRiAACmgADyJRkFCxl4eFc7yVqHgQ")
            files, offset, total_results = await get_search_results(search.lower(), offset=0, filter=True)
            await searching.delete() 

            if not files:
                if settings["spell_check"]:
                    return await advantage_spell_chok(msg)
                else:
                    # MODIFIED: आपकी रिक्वेस्ट के अनुसार "Movie not found" का मैसेज बदला गया
                    not_found_text = (
                        "**षमा करें, हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌**\n\n"
                        "**sᴏʀʀʏ, ᴡᴇ ʜᴀᴠᴇɴ'ᴛ ғɪɴᴅ ʏᴏᴜʀ ғɪʟᴇ. ᴍᴀʏʙᴇ ʏᴏᴜ ᴍᴀᴅᴇ ᴀ ᴍɪsᴛᴀᴋᴇ? ᴘʟᴇᴀsᴇ ᴛʀʏ ᴛᴏ ᴡʀɪᴛᴇ ᴄᴏʀʀᴇᴄᴛʟʏ 😊**\n"
                        "_____________________\n\n"
                        "**sᴇᴀʀᴄʜ sᴇᴄᴏɴᴅ ʙᴏᴛ - @asfilter_bot**"
                    )
                    not_found_message = await msg.reply_text(not_found_text, quote=True, parse_mode=enums.ParseMode.MARKDOWN)
                    # NEW: नॉट फाउंड मैसेज को 10 सेकंड बाद हटाने के लिए शेड्यूल किया गया
                    asyncio.create_task(schedule_delete(not_found_message, 10))
                    return
        else:
            return
    else:
        # If from spell check, use the message the search was initiated from
        message = msg.message.reply_to_message
        settings = await get_settings(message.chat.id)
        search, files, offset, total_results = spoll
        
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"📁 {to_fancy_font(file.file_name)}",
                    callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"📂 {to_fancy_font(file.file_name)}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
                InlineKeyboardButton(
                    text=f"💾 {to_fancy_font(get_size(file.file_size))}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
            ]
            for file in files
        ]

    # Create key for BUTTONS dictionary - FIXED: key variable is now properly defined
    key = f"{message.chat.id}-{message.id}"
    BUTTONS[key] = search

    # Filter buttons row
    btn.append([
        InlineKeyboardButton(text="🎬 Qᴜᴀʟɪᴛʏ", callback_data="quality_dummy"),
        InlineKeyboardButton(text="🌐 Lᴀɴɢᴜᴀɢᴇ", callback_data="language_dummy"),
        InlineKeyboardButton(text="📺 Sᴇᴀsᴏɴ", callback_data="season_dummy")
    ])
    
    # Chennai Express specific session buttons
    chennai_sessions = []
    for i in range(1, 51):
        session_num = f"{i:02d}"
        chennai_sessions.append(
            InlineKeyboardButton(
                text=f"S{session_num}", 
                callback_data=f"session_{session_num}"
            )
        )
    
    # Add session buttons in rows of 5
    for i in range(0, len(chennai_sessions), 5):
        btn.append(chennai_sessions[i:i+5])
    
    # Indian language buttons
    indian_languages = [
        ("Hindi", "lang_hindi"),
        ("Tamil", "lang_tamil"), 
        ("Telugu", "lang_telugu"),
        ("Malayalam", "lang_malayalam"),
        ("Kannada", "lang_kannada"),
        ("Bengali", "lang_bengali"),
        ("Marathi", "lang_marathi"),
        ("Gujarati", "lang_gujarati"),
        ("Punjabi", "lang_punjabi")
    ]
    
    lang_buttons = []
    for lang_name, lang_data in indian_languages:
        lang_buttons.append(
            InlineKeyboardButton(
                text=to_fancy_font(lang_name),
                callback_data=lang_data
            )
        )
    
    # Add language buttons in rows of 3
    for i in range(0, len(lang_buttons), 3):
        btn.append(lang_buttons[i:i+3])
    
    # Send All Files button - FIXED: Now key is properly defined
    btn.append([
        InlineKeyboardButton(
            text="🚀 Sᴇɴᴅ Aʟʟ Fɪʟᴇs", 
            callback_data=f"sendall_{key}"
        )
    ])
    
    # Check Bot PM button
    btn.append([
        InlineKeyboardButton(
            text="🔍 Cʜᴇᴄᴋ Bᴏᴛ PM", 
            url=f"https://t.me/{temp.U_NAME}"
        )
    ])

    # Pagination - FIX 2: Ensure offset is an integer before arithmetic and comparison
    req = message.from_user.id if message.from_user else 0
    
    # Convert offset to integer safely
    try:
        int_offset = int(offset)
    except ValueError:
        int_offset = 0

    current_page = math.ceil(int_offset / 10) + 1
    total_pages = math.ceil(total_results / 10)
    
    pagination_buttons = []
    
    if int_offset > 0:
        pagination_buttons.append(
            InlineKeyboardButton("⏪ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{int_offset-10}")
        )
    
    pagination_buttons.append(
        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages")
    )
    
    if int_offset + 10 < total_results:
        pagination_buttons.append(
            InlineKeyboardButton("Nᴇxᴛ ⏩", callback_data=f"next_{req}_{key}_{int_offset+10}")
        )
    
    if pagination_buttons:
        btn.append(pagination_buttons)

    # Custom Message
    user_mention = message.from_user.mention if message.from_user else 'Usᴇʀ'
    chat_title = message.chat.title if message.chat.title else 'ᴛʜɪs ɢʀᴏᴜᴘ'
    
    custom_msg = f"""
**[ 📂 ʜᴇʀᴇ ɪ ғᴏᴜɴᴅ ғᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ >{search}<**

**📢 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ - >{user_mention}<**
**♾️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ - >{chat_title}<**

**🍿 Yᴏᴜʀ ᴍᴏᴠɪᴇ ғɪʟᴇs 👇**]
"""

    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    TEMPLATE = settings['template']
    if imdb:
        cap = TEMPLATE.format(
            query=search,
            title=imdb['title'],
            votes=imdb['votes'],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb['box_office'],
            localized_title=imdb['localized_title'],
            kind=imdb['kind'],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb['release_date'],
            year=imdb['year'],
            genres=imdb['genres'],
            poster=imdb['poster'],
            plot=imdb['plot'],
            rating=imdb['rating'],
            url=imdb['url'],
            **locals()
        )
        cap += "\n\n" + custom_msg
    else:
        cap = custom_msg
        
    sent_message = None
    if imdb and imdb.get('poster'):
        try:
            sent_message = await message.reply_photo(photo=imdb.get('poster'), caption=cap[:1024],
                                      reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.MARKDOWN)
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            sent_message = await message.reply_photo(photo=poster, caption=cap[:1024], reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.MARKDOWN)
        except Exception as e:
            logger.exception(e)
            sent_message = await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.MARKDOWN)
    else:
        sent_message = await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.MARKDOWN)

    # Schedule deletion of result message after 10 minutes
    if sent_message:
        asyncio.create_task(schedule_delete(sent_message, 600))
        
    if spoll:
        # Delete the spell check message
        await msg.message.delete()

async def advantage_spell_chok(msg):
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", msg.text, flags=re.IGNORECASE)
    query = query.strip() + " movie"
    
    g_s = await search_gagala(query)
    await asyncio.sleep(1)
    g_s += await search_gagala(msg.text)
    
    gs_parsed = []
    if not g_s:
        not_found_text = (
            "**षमा करें, हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌**\n\n"
            "**sᴏʀʀʏ, ᴡᴇ ʜᴀᴠᴇɴ'ᴛ ғɪɴᴅ ʏᴏᴜʀ ғɪʟᴇ. ᴍᴀʏʙᴇ ʏᴏᴜ ᴍᴀᴅᴇ ᴀ ᴍɪsᴛᴀᴋᴇ? ᴘʟᴇᴀsᴇ ᴛʀʏ ᴛᴏ ᴡʀɪᴛᴇ ᴄᴏʀʀᴇᴄᴛʟʏ 😊**\n"
            "_____________________\n\n"
            "**sᴇᴀʀᴄʜ sᴇᴄᴏɴᴅ ʙᴏᴛ - @asfilter_bot**"
        )
        k = await msg.reply_text(not_found_text, parse_mode=enums.ParseMode.MARKDOWN)
        asyncio.create_task(schedule_delete(k, 8))
        return
    regex = re.compile(r".*(imdb|wikipedia).*", re.IGNORECASE)
    gs = list(filter(regex.match, g_s))
    gs_parsed = [re.sub(
        r'\b(\-([a-zA-Z-\s])\-\simdb|(\-\s)?imdb|(\-\s)?wikipedia|\(|\)|\-|reviews|full|all|episode(s)?|film|movie|series)',
        '', i, flags=re.IGNORECASE) for i in gs]
    if not gs_parsed:
        reg = re.compile(r"watch(\s[a-zA-Z0-9_\s\-\(\)]*)*\|.*",
                         re.IGNORECASE)
        for mv in g_s:
            match = reg.match(mv)
            if match:
                # Use group(1) if it exists, otherwise just the whole match or a part of it
                # Assuming group(1) captures the movie title part
                if match.groups():
                    gs_parsed.append(match.group(1))
                else:
                    # Fallback if the regex structure changed or is unexpected
                    gs_parsed.append(mv.split('|')[0].strip().replace('watch', '').strip())
    user = msg.from_user.id if msg.from_user else 0
    movielist = []
    gs_parsed = list(dict.fromkeys(gs_parsed))
    if len(gs_parsed) > 3:
        gs_parsed = gs_parsed[:3]
    if gs_parsed:
        for mov in gs_parsed:
            imdb_s = await get_poster(mov.strip(), bulk=True)
            if imdb_s:
                movielist += [movie.get('title') for movie in imdb_s]
    movielist += [(re.sub(r'(\-|\(|\)|_)', '', i, flags=re.IGNORECASE)).strip() for i in gs_parsed]
    movielist = list(dict.fromkeys(movielist))
    if not movielist:
        not_found_text = (
            "**षमा करें, हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌**\n\n"
            "**sᴏʀʀʏ, ᴡᴇ ʜᴀᴠᴇɴ'ᴛ ғɪɴᴅ ʏᴏᴜʀ ғɪʟᴇ. ᴍᴀʏʙᴇ ʏᴏᴜ ᴍᴀᴅᴇ ᴀ ᴍɪsᴛᴀᴋᴇ? ᴘʟᴇᴀsᴇ ᴛʀʏ ᴛᴏ ᴡʀɪᴛᴇ ᴄᴏʀʀᴇᴄᴛʟʏ 😊**\n"
            "_____________________\n\n"
            "**sᴇᴀʀᴄʜ sᴇᴄᴏɴᴅ ʙᴏᴛ - @asfilter_bot**"
        )
        k = await msg.reply_text(not_found_text, parse_mode=enums.ParseMode.MARKDOWN)
        asyncio.create_task(schedule_delete(k, 8))
        return
    SPELL_CHECK[msg.id] = movielist
    btn = [[
        InlineKeyboardButton(
            text=to_fancy_font(movie.strip()),
            callback_data=f"spolling#{user}#{k}",
        )
    ] for k, movie in enumerate(movielist)]
    btn.append([InlineKeyboardButton(text=to_fancy_font("🔐 ᴄʟᴏsᴇ"), callback_data=f'spolling#{user}#close_spellcheck')])
    spell_check_message = await msg.reply("ɪ ᴄᴏᴜʟᴅɴ'ᴛ ғɪɴᴅ ᴀɴʏᴛʜɪɴɢ ʀᴇʟᴀᴛᴅ ᴛᴏ ᴛʜᴀᴛ\nᴅɪᴅ ʏᴏᴜ ᴍᴇᴀɴ ᴀɴʏ ᴏɴᴇ ᴏғ ᴛʜᴇsᴇ?",
                    reply_markup=InlineKeyboardMarkup(btn))
    asyncio.create_task(schedule_delete(spell_check_message, 60))

async def manual_filters(client, message, text=False):
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_filters(group_id)
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            # Use message.reply_text for better flow
                            await message.reply_text(reply_text, disable_web_page_preview=True)
                        else:
                            button_structure = eval(btn)
                            # Apply fancy font to buttons
                            for row in button_structure:
                                for button in row:
                                    if 'text' in button:
                                        button['text'] = to_fancy_font(button['text'])
                            
                            button = InlineKeyboardMarkup(button_structure)
                            await message.reply_text(
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=button
                            )
                    elif btn == "[]":
                        await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                        )
                    else:
                        button_structure = eval(btn)
                        # Apply fancy font to buttons
                        for row in button_structure:
                            for button in row:
                                if 'text' in button:
                                    button['text'] = to_fancy_font(button['text'])
                                    
                        button = InlineKeyboardMarkup(button_structure)
                        await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=button
                        )
                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False
