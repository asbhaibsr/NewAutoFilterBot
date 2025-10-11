import asyncio
import re
import ast
import math
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from database.connections_mdb import active_connection, all_connections, delete_connection, if_active, make_active, \
    make_inactive
from info import ADMINS, AUTH_CHANNEL, AUTH_USERS, CUSTOM_FILE_CAPTION, AUTH_GROUPS, P_TTI_SHOW_OFF, IMDB, \
    SINGLE_BUTTON, SPELL_CHECK_REPLY, IMDB_TEMPLATE
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import get_size, is_subscribed, get_poster, search_gagala, temp, get_settings, save_group_settings
from database.users_chats_db import db
from database.ia_filterdb import Media, get_file_details, get_search_results
from database.filters_mdb import (
    del_all,
    find_filter,
    get_filters,
)
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}

# Helper function to convert text to the desired fancy font
def to_fancy_font(text):
    """Converts a string to a fancy font style (small capitals/fancy letters)."""
    mapping = {
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ', 'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ',
        'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'Q', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ',
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ',
        'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'Q', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        '0': '𝟶', '1': '𝟷', '2': '𝟸', '3': '𝟹', '4': '𝟺', '5': '𝟻', '6': '𝟼', '7': '𝟽', '8': '𝟾', '9': '𝟿', 
        ' ': ' ', '/': '/', '#': '#', '_': '_', '-': '-', '[': '[', ']': ']', '(': '(', ')': ')', '{': '{', '}': '}', '<': '<', '>': '>'
    }
    return ''.join(mapping.get(char, char) for char in text)

# NEW: यह फंक्शन अब किसी भी मैसेज को दिए गए समय के बाद डिलीट कर सकता है
async def schedule_delete(message, delay_seconds):
    """Deletes the message after a specified delay."""
    await asyncio.sleep(delay_seconds)
    try:
        # सुनिश्चित करें कि मैसेज डिलीट करने लायक है (टेक्स्ट या मीडिया)
        if message and message.id:
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
    try:
        offset = int(offset)
    except:
        offset = 0
    search = BUTTONS.get(key)
    if not search:
        await query.answer("You are using one of my old messages, please send the request again.", show_alert=True)
        return

    files, n_offset, total = await get_search_results(search, offset=offset, filter=True)
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0

    if not files:
        return

    settings = await get_settings(query.message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings['button']:
        btn = [
            [
                # MODIFIED: बटन फ़ॉन्ट और इमोजी का उपयोग
                InlineKeyboardButton(
                    text=f"[{to_fancy_font(get_size(file.file_size))}] {to_fancy_font(file.file_name)}", callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        btn = [
            [
                # MODIFIED: बटन फ़ॉन्ट और इमोजी का उपयोग
                InlineKeyboardButton(
                    text=f"📂 {to_fancy_font(file.file_name)}", callback_data=f'{pre}#{file.file_id}'
                ),
                InlineKeyboardButton(
                    text=f"💾 {to_fancy_font(get_size(file.file_size))}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
            ]
            for file in files
        ]

    current_page = math.ceil(int(offset) / 10) + 1
    total_pages = math.ceil(total / 10)
    
    off_set = offset - 10 if offset > 0 else None

    next_btn = f"next_{req}_{key}_{n_offset}" if n_offset != 0 else None

    # MODIFIED: चेतावनी संदेश हटाने के लिए नए डमी कॉलबैक (फ़ॉन्ट और इमोजी के साथ)
    btn.append(
        [
            InlineKeyboardButton(text=to_fancy_font("Qᴜᴀʟɪᴛʏ"), callback_data="filter_q_dummy"),
            InlineKeyboardButton(text=to_fancy_font("Lᴀɴɢᴜᴀɢᴇ"), callback_data="filter_l_dummy"),
            InlineKeyboardButton(text=to_fancy_font("Sᴇᴀsᴏɴ"), callback_data="filter_s_dummy")
        ]
    )
    
    # NEW: 'Check Bot PM For File' बटन जोड़ा गया (फ़ॉन्ट और इमोजी के साथ)
    btn.append(
        [InlineKeyboardButton(text="👉 ᴄʜᴇᴄᴋ ʙᴏᴛ ᴘᴍ ғᴏʀ ғɪʟᴇ 👈", url=f"https://t.me/{temp.U_NAME}")]
    )
    
    # MODIFIED: पेजिनेशन बटन (आपकी आवश्यकतानुसार)
    pagination_buttons = []
    
    # MODIFIED: '⏪ BACK' बटन का फ़ॉन्ट और इमोजी
    if off_set is not None:
        pagination_buttons.append(InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"))
    
    # MODIFIED: पेजिनेशन टेक्स्ट (Pages Button) का फ़ॉन्ट और इमोजी
    # पुरानी रिक्वेस्ट: [No more page available] -> इसे सिर्फ तभी दिखाना चाहिए जब आगे कोई पेज न हो।
    # Pagination Logic:
    if off_set is None and next_btn is None: # Only 1 page
         pagination_buttons.append(InlineKeyboardButton("🗓 ғɪʟᴇs 𝟷/𝟷", callback_data="pages"))
    elif off_set is not None or next_btn is not None:
        pagination_buttons.append(InlineKeyboardButton(f"🗓 ᴘᴀɢᴇs {current_page}/{total_pages}", callback_data="pages"))
    
    # MODIFIED: 'NEXT ⏩' बटन का फ़ॉन्ट और इमोजी
    if next_btn is not None:
        pagination_buttons.append(InlineKeyboardButton("ɴᴇxᴛ »", callback_data=next_btn))

    if pagination_buttons:
        btn.append(pagination_buttons)


    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass
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
    k = await manual_filters(bot, query.message, text=movie)
    if k == False:
        files, offset, total_results = await get_search_results(movie, offset=0, filter=True)
        if files:
            k = (movie, files, offset, total_results)
            await auto_filter(bot, query, k)
        else:
            k = await query.message.edit('This Movie Not Found In DataBase')
            # MODIFIED: संदेश को 10 सेकंड बाद हटाने के लिए शेड्यूल किया गया
            asyncio.create_task(schedule_delete(k, 10))


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await query.message.delete()
        
    # NEW: आपके डमी बटनों के लिए हैंडलर (चेतावनी संदेश हटा दिया गया)
    elif query.data in ["filter_q_dummy", "filter_l_dummy", "filter_s_dummy"]:
        # query.answer() without a message will just close the loading animation
        await query.answer() 
    
    elif query.data.startswith("sendall"):
        # SEND ALL बटन के लिए डमी हैंडलर
        await query.answer("sᴇɴᴅ ᴀʟʟ फ़ीचर के लिए कृपया ᴘᴍ में जाँच करें।", show_alert=True)
    
    # बाकी cb_handler लॉजिक
    
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
            await query.message.reply_to_message.delete()
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
            
            # NEW: आपकी रिक्वेस्ट के अनुसार फ़ाइल के साथ चेतावनी मैसेज
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
        # NEW: फाइल को 5 मिनट (300 सेकंड) बाद डिलीट करने के लिए शेड्यूल किया गया
        asyncio.create_task(schedule_delete(sent_msg, 300))

# ... (बाकी का cb_handler और अन्य फंक्शन्स का कोड जैसा था वैसा ही रहेगा) ...
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

        if status == "True":
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
        settings = await get_settings(msg.message.chat.id)
        message = msg.message.reply_to_message
        search, files, offset, total_results = spoll
        
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                # MODIFIED: बटन फ़ॉन्ट और इमोजी का उपयोग
                InlineKeyboardButton(
                    text=f"[{to_fancy_font(get_size(file.file_size))}] {to_fancy_font(file.file_name)}", callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        btn = [
            [
                # MODIFIED: बटन फ़ॉन्ट और इमोजी का उपयोग
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

    # MODIFIED: चेतावनी संदेश हटाने के लिए नए डमी कॉलबैक (फ़ॉन्ट और इमोजी के साथ)
    key = f"{message.chat.id}-{message.id}"
    btn.append(
        [
            InlineKeyboardButton(text=to_fancy_font("Qᴜᴀʟɪᴛʏ"), callback_data="filter_q_dummy"),
            InlineKeyboardButton(text=to_fancy_font("Lᴀɴɢᴜᴀɢᴇ"), callback_data="filter_l_dummy"),
            InlineKeyboardButton(text=to_fancy_font("Sᴇᴀsᴏɴ"), callback_data="filter_s_dummy")
        ]
    )
    
    # NEW: 'Check Bot PM For File' बटन जोड़ा गया (फ़ॉन्ट और इमोजी के साथ)
    btn.append(
        [InlineKeyboardButton(text="👉 ᴄʜᴇᴄᴋ ʙᴏᴛ ᴘᴍ ғᴏʀ ғɪʟᴇ 👈", url=f"https://t.me/{temp.U_NAME}")]
    )
    
    # MODIFIED: पेजिनेशन बटन (आपकी आवश्यकतानुसार)
    pagination_buttons = []
    
    req = message.from_user.id if message.from_user else 0
    total_pages = math.ceil(int(total_results) / 10)
    current_page = 1 # Always 1 on initial load

    if offset != "":
        BUTTONS[key] = search
        # Initial load, only NEXT is possible (unless offset is a specific value > 0, which it isn't here)
        pagination_buttons.append(InlineKeyboardButton(f"🗓 ᴘᴀɢᴇs {current_page}/{total_pages}", callback_data="pages"))
        pagination_buttons.append(InlineKeyboardButton(text="ɴᴇxᴛ »", callback_data=f"next_{req}_{key}_{offset}"))
    else:
        # No more pages
        pagination_buttons.append(InlineKeyboardButton(text="🗓 ғɪʟᴇs 𝟷/𝟷", callback_data="pages"))
    
    if pagination_buttons:
        btn.append(pagination_buttons)

    # MODIFIED: आपकी रिक्वेस्ट के अनुसार मैसेज फॉर्मेट (Movie Found)
    user_mention = message.from_user.mention if message.from_user else 'Usᴇʀ'
    chat_title = message.chat.title if message.chat.title else 'ᴛʜɪs ɢʀᴏᴜᴘ'
    
    # Custom Message
    custom_msg = f"""
**[ 📂 ʜᴇʀᴇ ɪ ғᴏᴜɴᴅ ғᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ >{search}<**

**📢 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ - >{user_mention}<**
**♾️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ - >{chat_title}<**

**🍿 Yᴏᴜʀ ᴍᴏᴠɪᴇ ғɪʟᴇs 👇**]
"""

    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    TEMPLATE = settings['template']
    if imdb:
        # If IMDB is enabled, we use the IMDB template first
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
        
        # Then append the custom movie files message
        cap += "\n\n" + custom_msg
        
    else:
        # If IMDB is disabled, just use the custom message
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

    # NEW: ग्रुप में भेजे गए रिजल्ट को 10 मिनट (600 सेकंड) बाद डिलीट करने के लिए शेड्यूल किया गया
    if sent_message:
        asyncio.create_task(schedule_delete(sent_message, 600))
        
    if spoll:
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
        # MODIFIED: आपकी रिक्वेस्ट के अनुसार "Movie not found" का मैसेज बदला गया
        not_found_text = (
            "**षमा करें, हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌**\n\n"
            "**sᴏʀʀʏ, ᴡᴇ ʜᴀᴠᴇɴ'ᴛ ғɪɴᴅ ʏᴏᴜʀ ғɪʟᴇ. ᴍᴀʏʙᴇ ʏᴏᴜ ᴍᴀᴅᴇ ᴀ ᴍɪsᴛᴀᴋᴇ? ᴘʟᴇᴀsᴇ ᴛʀʏ ᴛᴏ ᴡʀɪᴛᴇ ᴄᴏʀʀᴇᴄᴛʟʏ 😊**\n"
            "_____________________\n\n"
            "**sᴇᴀʀᴄʜ sᴇᴄᴏɴᴅ ʙᴏᴛ - @asfilter_bot**"
        )
        k = await msg.reply_text(not_found_text, parse_mode=enums.ParseMode.MARKDOWN)
        # MODIFIED: संदेश को 8 सेकंड बाद हटाने के लिए शेड्यूल किया गया
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
                gs_parsed.append(match.group(1))
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
        # MODIFIED: आपकी रिक्वेस्ट के अनुसार "Movie not found" का मैसेज बदला गया
        not_found_text = (
            "**षमा करें, हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌**\n\n"
            "**sᴏʀʀʏ, ᴡᴇ ʜᴀᴠᴇɴ'ᴛ ғɪɴᴅ ʏᴏᴜʀ ғɪʟᴇ. ᴍᴀʏʙᴇ ʏᴏᴜ ᴍᴀᴅᴇ ᴀ ᴍɪsᴛᴀᴋᴇ? ᴘʟᴇᴀsᴇ ᴛʀʏ ᴛᴏ ᴡʀɪᴛᴇ ᴄᴏʀʀᴇᴄᴛʟʏ 😊**\n"
            "_____________________\n\n"
            "**sᴇᴀʀᴄʜ sᴇᴄᴏɴᴅ ʙᴏᴛ - @asfilter_bot**"
        )
        k = await msg.reply_text(not_found_text, parse_mode=enums.ParseMode.MARKDOWN)
        # MODIFIED: संदेश को 8 सेकंड बाद हटाने के लिए शेड्यूल किया गया
        asyncio.create_task(schedule_delete(k, 8))
        return
    SPELL_CHECK[msg.id] = movielist
    btn = [[
        InlineKeyboardButton(
            # MODIFIED: बटन फ़ॉन्ट का उपयोग
            text=to_fancy_font(movie.strip()),
            callback_data=f"spolling#{user}#{k}",
        )
    ] for k, movie in enumerate(movielist)]
    # MODIFIED: बटन फ़ॉन्ट का उपयोग
    btn.append([InlineKeyboardButton(text=to_fancy_font("🔐 ᴄʟᴏsᴇ"), callback_data=f'spolling#{user}#close_spellcheck')])
    spell_check_message = await msg.reply("ɪ ᴄᴏᴜʟᴅɴ'ᴛ ғɪɴᴅ ᴀɴʏᴛʜɪɴɢ ʀᴇʟᴀᴛᴇᴅ ᴛᴏ ᴛʜᴀᴛ\nᴅɪᴅ ʏᴏᴜ ᴍᴇᴀɴ ᴀɴʏ ᴏɴᴇ ᴏғ ᴛʜᴇsᴇ?",
                    reply_markup=InlineKeyboardMarkup(btn))
    # NEW: स्पेल चेक मैसेज को 60 सेकंड बाद डिलीट करने के लिए शेड्यूल किया गया
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
                            await client.send_message(group_id, reply_text, disable_web_page_preview=True)
                        else:
                            # MODIFIED: बटन फ़ॉन्ट को मैनुअल फिल्टर के बटनों पर भी अप्लाई किया गया है
                            # Note: eval(btn) will load the button structure, then we modify the text.
                            button_structure = eval(btn)
                            for row in button_structure:
                                for button in row:
                                    # Assuming button is an InlineKeyboardButton, modify its text
                                    if 'text' in button:
                                        button['text'] = to_fancy_font(button['text'])
                            
                            button = InlineKeyboardMarkup(button_structure)
                            await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=button,
                                reply_to_message_id=reply_id
                            )
                    elif btn == "[]":
                        await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                    else:
                        # MODIFIED: बटन फ़ॉन्ट को मैनुअल फिल्टर के बटनों पर भी अप्लाई किया गया है
                        button_structure = eval(btn)
                        for row in button_structure:
                            for button in row:
                                if 'text' in button:
                                    button['text'] = to_fancy_font(button['text'])
                                    
                        button = InlineKeyboardMarkup(button_structure)
                        await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=button,
                            reply_to_message_id=reply_id
                        )
                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False
