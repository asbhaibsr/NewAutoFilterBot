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

QUALITY_OPTIONS = [
    ("360P", "360P"), ("480P", "480P"), ("720P", "720P"),
    ("1080P", "1080P"), ("1440P", "1440P"), ("2160P", "2160P"),
    ("4K", "4K"), ("2K", "2K"), ("BluRay", "BluRay"),
    ("HD Rip", "HD Rip"), ("Web-DL", "Web-DL"), ("HDRip", "HDRip")
]

INDIAN_LANGUAGES = [
    ("Hindi", "Hindi"), ("Tamil", "Tamil"),
    ("Telugu", "Telugu"), ("Malayalam", "Malayalam"),
    ("Kannada", "Kannada"), ("Bengali", "Bengali"),
    ("Marathi", "Marathi"), ("Gujarati", "Gujarati"),
    ("Punjabi", "Punjabi"), ("English", "English")
]

SEASON_OPTIONS = [f"Season {i}" for i in range(1, 51)]

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
        '(': '(', ')': ')', '[': '[', ']': ']', '{': '{', '}': '}',
        '@': '@', '#': '#', '$': '$', '%': '%', '&': '&', '*': '*', '+': '+', '=': '=',
        ':': ':', ';': ';', '<': '<', '>': '>'
    }
    return ''.join(mapping.get(char, char) for char in text)

async def schedule_delete(message, delay_seconds):
    await asyncio.sleep(delay_seconds)
    try:
        if message and hasattr(message, 'id') and message.id:
            await message.delete()
    except Exception as e:
        logger.warning(f"Error deleting message: {e}")

def create_filter_buttons(filter_type, key, current_state=None):
    buttons = []
    
    if filter_type == "quality":
        options = QUALITY_OPTIONS
        current_selection = current_state.get('quality') if current_state else None
    elif filter_type == "language":
        options = INDIAN_LANGUAGES
        current_selection = current_state.get('language') if current_state else None
    elif filter_type == "season":
        options = [(s, s) for s in SEASON_OPTIONS]
        current_selection = current_state.get('season') if current_state else None
    else:
        return [InlineKeyboardButton(text=to_fancy_font("Back To Files"), callback_data=f"back_to_files#{key}")]

    items_per_row = 3 if filter_type in ["quality", "language"] else 2
    
    for i in range(0, len(options), items_per_row):
        row = []
        for name, data in options[i:i+items_per_row]:
            text = f"✅ {name}" if current_selection == data else name
            row.append(
                InlineKeyboardButton(
                    text=to_fancy_font(text),
                    callback_data=f"filter_{filter_type}_{data}#{key}"
                )
            )
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(text=to_fancy_font("Back To Files"), callback_data=f"back_to_files#{key}")])
    return buttons

async def build_results_buttons(client, query_or_message, key, search, language, quality, season, offset):
    """Helper function to build the results message and buttons"""
    
    files, n_offset, total_results = await get_search_results(
        search, 
        offset=offset, 
        filter=True, 
        language=language, 
        quality=quality, 
        season=season
    )

    # Store results for this page to avoid re-fetching for individual file sends
    BUTTONS[key] = {
        'search': search, 
        'offset': n_offset, 
        'total_results': total_results, 
        'language': language,
        'quality': quality,
        'season': season,
        'files': files  # Store the actual file objects
    }
    
    chat_id = query_or_message.message.chat.id if isinstance(query_or_message, CallbackQuery) else query_or_message.chat.id
    from_user = query_or_message.from_user
    
    settings = await get_settings(chat_id)
    pre = 'filep' if settings['file_secure'] else 'file'
    
    btn = []
    
    # File buttons with new callback data including index
    if files:
        for i, file in enumerate(files):
            btn.append([
                InlineKeyboardButton(
                    text=f"📁 {file.file_name} - {get_size(file.file_size)}",
                    callback_data=f'{pre}#{key}#{i}' # Format: pre#key#index
                )
            ])
    
    # Pagination Buttons (Moved Up)
    req = from_user.id if from_user else 0
    current_page = math.ceil(offset / 10) + 1
    total_pages = math.ceil(total_results / 10)
    
    pagination_buttons = []
    if offset > 0:
        pagination_buttons.append(InlineKeyboardButton(to_fancy_font("Back"), callback_data=f"next_{req}_{key}_{offset-10}"))
    
    pagination_buttons.append(InlineKeyboardButton(to_fancy_font(f"{current_page}/{total_pages}"), callback_data="pages"))
    
    if n_offset != 0 and n_offset < total_results:
        pagination_buttons.append(InlineKeyboardButton(to_fancy_font("Next"), callback_data=f"next_{req}_{key}_{n_offset}"))
    
    if pagination_buttons:
        btn.append(pagination_buttons)
        
    # "Select Options" button
    if files:
        btn.append([InlineKeyboardButton(text="👇 Sᴇʟᴇᴄᴛ Yᴏᴜʀ Oᴘᴛɪᴏɴs 👇", callback_data="pages")])
    
    # Filter buttons row
    btn.append([
        InlineKeyboardButton(text=to_fancy_font(f"Quality ({quality or 'None'})"), callback_data=f"open_filter#quality#{key}"),
        InlineKeyboardButton(text=to_fancy_font(f"Language ({language or 'None'})"), callback_data=f"open_filter#language#{key}")
    ])
    
    btn.append([
        InlineKeyboardButton(text=to_fancy_font(f"Season ({season or 'None'})"), callback_data=f"open_filter#season#{key}"),
        InlineKeyboardButton(text=to_fancy_font("Send All Files"), callback_data=f"sendall_{key}")
    ])
        
    btn.append([
        InlineKeyboardButton(
            text=to_fancy_font("Check Bot PM"), 
            url=f"https://t.me/{temp.U_NAME}"
        )
    ])

    user_mention = f"[{from_user.first_name}](tg://user?id={from_user.id})" if from_user else 'User'
    chat = query_or_message.message.chat if isinstance(query_or_message, CallbackQuery) else query_or_message.chat
    chat_title = chat.title if chat.title else 'This Group'
    
    filters_applied = f"**Filters:** Q: `{quality or 'None'}`, L: `{language or 'None'}`, S: `{season or 'None'}`"
    
    custom_msg = f"""
**Here I Found For Your Search: {search}**
{filters_applied}

**Requested By:** {user_mention}
**Powered By: {chat_title}**

**Your Movie Files ({total_results})**
"""
    return custom_msg, InlineKeyboardMarkup(btn), files

async def run_filtered_search(client, query, key, back_to_main=False):
    search_data = BUTTONS.get(key)
    if not search_data:
        return await query.message.edit_text("Search expired. Please search again.")

    offset = 0 if not back_to_main else search_data.get('offset', 0)
    
    text, markup, _ = await build_results_buttons(
        client, query, key,
        search_data['search'],
        search_data['language'],
        search_data['quality'],
        search_data['season'],
        offset=search_data.get('offset', 0)
    )
    
    try:
        await query.message.edit_text(text=text, reply_markup=markup, parse_mode=enums.ParseMode.MARKDOWN)
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error editing message: {e}")


@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    k = await manual_filters(client, message)
    if k == False:
        await auto_filter(client, message)

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset_str = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer("This is not for you!", show_alert=True)
        
    offset = int(offset_str)
    
    search_data = BUTTONS.get(key)
    if not search_data:
        await query.answer("Search expired. Please search again.", show_alert=True)
        return

    text, markup, _ = await build_results_buttons(
        bot, query, key,
        search_data['search'],
        search_data['language'],
        search_data['quality'],
        search_data['season'],
        offset
    )
        
    await query.message.edit_text(text=text, reply_markup=markup, parse_mode=enums.ParseMode.MARKDOWN)
    await query.answer()

@Client.on_callback_query(filters.regex(r"^sendall"))
async def send_all_files(bot, query):
    _, key = query.data.split("_")
    
    search_data = BUTTONS.get(key)
    if not search_data:
        await query.answer("Search expired. Please search again.", show_alert=True)
        return
    
    await query.answer("Sending all files to your PM...", show_alert=True)
    
    search = search_data['search']
    current_language = search_data['language']
    current_quality = search_data['quality']
    current_season = search_data['season']
    
    all_files = []
    offset = 0
    while True:
        files, next_offset, total = await get_search_results(
            search, 
            offset=offset, 
            max_results=100, 
            filter=True,
            language=current_language, 
            quality=current_quality, 
            season=current_season
        )
        all_files.extend(files)
        
        try:
            next_offset = int(next_offset)
        except:
            next_offset = 0

        if next_offset == 0 or len(all_files) >= 1000:
            break
        offset = next_offset
    
    if not all_files:
        notification = await query.message.reply_text("No files found to send with the current filters.")
        asyncio.create_task(schedule_delete(notification, 10))
        return
    
    user_id = query.from_user.id
    sent_count = 0
    
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
            
            sent_msg = await bot.send_cached_media(
                chat_id=user_id,
                file_id=file.file_id,
                caption=file_caption,
                protect_content=True 
            )
            
            warning_message = f"""
**ʜᴇʟʟᴏ** {query.from_user.mention},

**⚠️ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ 5 ᴍɪɴᴜᴛᴇs**

**ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇ sᴏᴍᴇᴡʜᴇʀᴇ ʙᴇғᴏʀᴇ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ..**

**मूवी यहां डाउनलोड ना करे क्योंकि | मूवी 🍿 5 Minutes में डिलीट कर दी जायेगी**
**कृपया कही फॉरवर्ड करे के डाउनलोड करे**
"""
            
            await sent_msg.reply_text(warning_message, quote=True)
            sent_count += 1
            
            asyncio.create_task(schedule_delete(sent_msg, 300))
            await asyncio.sleep(0.5)
            
        except UserIsBlocked:
            await query.message.reply_text("Please unblock the bot first!")
            return
        except PeerIdInvalid:
             await query.message.reply_text("Please start the bot in private chat first!", 
                                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Start Bot", url=f"https://t.me/{temp.U_NAME}")]])
                                           )
             return
        except Exception as e:
            logger.error(f"Error sending file {file.file_name}: {e}")
            continue
    
    filters_applied = f"**Filters:** Q: `{current_quality or 'None'}`, L: `{current_language or 'None'}`, S: `{current_season or 'None'}`"
    notification = await query.message.reply_text(
        f"✅ Successfully sent {sent_count} files to your PM!\n"
        f"📁 Files will be auto-deleted in 5 minutes.\n"
        f"🔍 Search: `{search}`\n"
        f"{filters_applied}"
    )
    
    asyncio.create_task(schedule_delete(notification, 10))

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
    
    elif query.data.startswith("open_filter#"):
        await query.answer()
        _, filter_type, key = query.data.split("#")
        
        search_data = BUTTONS.get(key)
        if not search_data:
            return await query.message.edit_text("Search expired. Please search again.")

        filter_buttons = create_filter_buttons(filter_type, key, search_data)
        
        if filter_type == "quality":
            title = "SELECT QUALITY ↓"
        elif filter_type == "language":
            title = "SELECT LANGUAGE ↓"  
        elif filter_type == "season":
            title = "SELECT SEASON ↓"
        else:
            title = "Select Filter"
            
        await query.message.edit_text(
            text=title,
            reply_markup=InlineKeyboardMarkup(filter_buttons)
        )

    elif query.data.startswith("filter_"):
        parts = query.data.split("_", 2)
        filter_type = parts[1]
        filter_value_and_key = parts[2]
        filter_value, key = filter_value_and_key.split("#")
        
        search_data = BUTTONS.get(key)
        if not search_data:
            return await query.answer("Search expired. Please search again.", show_alert=True)

        current_selection = search_data.get(filter_type)
        
        temp_search = search_data['search']
        temp_lang = search_data['language']
        temp_quality = search_data['quality']
        temp_season = search_data['season']
        
        new_value = None
        alert_msg = ""
        
        if current_selection == filter_value:
             new_value = None
             alert_msg = f"❌ {filter_type.capitalize()} filter removed."
        else:
             if filter_type == 'quality': temp_quality = filter_value
             elif filter_type == 'language': temp_lang = filter_value
             elif filter_type == 'season': temp_season = filter_value

             files_check, _, _ = await get_search_results(
                 temp_search, offset=0, max_results=1, 
                 language=temp_lang, quality=temp_quality, season=temp_season
             )
             
             if not files_check:
                 alert_msg = f"🚫 No file found for {filter_value} filter. Please choose another."
                 await query.answer(alert_msg, show_alert=True)
                 return

             new_value = filter_value
             alert_msg = f"✅ {filter_type.capitalize()} set to {filter_value}"
        
        search_data[filter_type] = new_value
        BUTTONS[key] = search_data

        await query.answer(alert_msg, show_alert=False)
        await run_filtered_search(client, query, key)

    elif query.data.startswith("back_to_files#"):
        _, key = query.data.split("#")
        await query.answer()
        await run_filtered_search(client, query, key, back_to_main=True)
    
    # FIX: Major change in individual file sending logic to prevent errors
    elif query.data.startswith("file"):
        try:
            ident, key, index_str = query.data.split("#")
            index = int(index_str)
        except (ValueError, IndexError):
            return await query.answer("Invalid request.", show_alert=True)

        search_data = BUTTONS.get(key)
        if not search_data or 'files' not in search_data:
            return await query.answer("This search has expired. Please search again.", show_alert=True)

        page_files = search_data['files']
        if index >= len(page_files):
            return await query.answer("File not found on this page. It might be an old message.", show_alert=True)
            
        files = page_files[index] # Get the file object directly from stored list
        file_id = files.file_id
            
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        settings = await get_settings(query.message.chat.id)
        
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name=title or '', file_size=size or '', file_caption=f_caption or '')
            except Exception as e:
                logger.exception(e)
        if f_caption is None:
            f_caption = f"{title}"

        if (AUTH_CHANNEL and not await is_subscribed(client, query)) or settings['botpm']:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
            return
        
        try:
            sent_msg = await client.send_cached_media(
                chat_id=query.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=True if ident == "filep" else False 
            )
            
            warning_message = f"""
**ʜᴇʟʟᴏ** {query.from_user.mention},

**⚠️ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ 5 ᴍɪɴᴜᴛᴇs**

**ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇ sᴏᴍᴇᴡʜᴇʀᴇ ʙᴇғᴏʀᴇ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ..**

**मूवी यहां डाउनलोड ना करे क्योंकि | मूवी 🍿 5 Minutes में डिलीट कर दी जायेगी**
**कृपया कही फॉरवर्ड करे के डाउनलोड करे**
"""
            
            await sent_msg.reply_text(warning_message, quote=True)
            asyncio.create_task(schedule_delete(sent_msg, 300))
            
            await query.answer('Check PM, I have sent the file. It will be deleted in 5 minutes.', show_alert=True)
            
        except UserIsBlocked:
            await query.answer('Unblock the bot first!', show_alert=True)
        except PeerIdInvalid:
            await query.answer("Please start the bot in private chat first!", url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}", show_alert=True)
        except Exception as e:
            logger.exception(f"Error sending file to PM: {e}")
            await query.answer(f"An error occurred: {e}", show_alert=True)

    elif query.data.startswith("checksub"):
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer("ɪ ʟɪᴋᴇ ʏᴏᴜʀ sᴍᴀʀᴛɴᴇss, ʙᴜᴛ ᴅᴏɴ'T ʙᴇ ᴏᴠᴇʀsᴍᴀʀᴛ 😒", show_alert=True)
            return
        ident, file_id = query.data.split("#")
        try:
            files_ = await get_file_details(file_id)
            if not files_:
                return await query.answer('ɴᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
            files = files_[0]
            title = files.file_name
            size = get_size(files.file_size)
            f_caption = files.caption
            if CUSTOM_FILE_CAPTION:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name=title or '', file_size=size or '', file_caption=f_caption or '')
            if f_caption is None:
                f_caption = f"{title}"
            await query.answer()
            sent_msg = await client.send_cached_media(
                chat_id=query.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=True if ident == 'checksubp' else False
            )
            asyncio.create_task(schedule_delete(sent_msg, 300))
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)


    elif query.data == "pages":
        await query.answer()
        
    # FIX: Handlers for Help and About buttons in PM
    elif query.data == "help":
        buttons = [[InlineKeyboardButton(to_fancy_font('Back'), callback_data='start'),
                    InlineKeyboardButton(to_fancy_font('Close'), callback_data='close_data')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.HELP_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    
    elif query.data == "about":
        buttons = [[InlineKeyboardButton(to_fancy_font('Back'), callback_data='start'),
                    InlineKeyboardButton(to_fancy_font('Close'), callback_data='close_data')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "start":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('Add Me To Your Groups'), url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ], [
            InlineKeyboardButton(to_fancy_font('Search'), switch_inline_query_current_chat=''),
            InlineKeyboardButton(to_fancy_font('Updates'), url='https://t.me/asbhai_bsr')
        ], [
            InlineKeyboardButton(to_fancy_font('Help'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('About'), callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
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
                    not_found_text = (
                        "**षमा करें, हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌**\n\n"
                        "**Sorry, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊**\n"
                        "_____________________\n\n"
                        "**Search second bot - @asfilter_bot**"
                    )
                    not_found_message = await msg.reply_text(not_found_text, quote=True, parse_mode=enums.ParseMode.MARKDOWN)
                    asyncio.create_task(schedule_delete(not_found_message, 10))
                    return
        else:
            return
    else:
        message = msg.message.reply_to_message
        settings = await get_settings(message.chat.id)
        search, files, offset, total_results = spoll
    
    key = f"{message.chat.id}-{message.id}"
    
    cap, btn, _ = await build_results_buttons(
        client, message, key, search, 
        language=None, quality=None, season=None, offset=0
    )

    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] and files else None
    
    if imdb:
        # Build caption with IMDB data
        TEMPLATE = settings['template']
        imdb_cap = TEMPLATE.format(
            query=search, title=imdb.get('title', ''), votes=imdb.get('votes', ''), aka=imdb.get("aka", ""), 
            seasons=imdb.get("seasons", ""), box_office=imdb.get('box_office', ''), localized_title=imdb.get('localized_title', ''), 
            kind=imdb.get('kind', ''), imdb_id=imdb.get("imdb_id", ""), cast=imdb.get("cast", ""), runtime=imdb.get("runtime", ""), 
            countries=imdb.get("countries", ""), certificates=imdb.get("certificates", ""), languages=imdb.get("languages", ""), 
            director=imdb.get("director", ""), writer=imdb.get("writer", ""), producer=imdb.get("producer", ""), 
            composer=imdb.get("composer", ""), cinematographer=imdb.get("cinematographer", ""), music_team=imdb.get("music_team", ""), 
            distributors=imdb.get("distributors", ""), release_date=imdb.get('release_date', ''), year=imdb.get('year', ''), 
            genres=imdb.get('genres', ''), poster=imdb.get('poster', ''), plot=imdb.get('plot', ''), 
            rating=imdb.get('rating', ''), url=imdb.get('url', ''), **locals()
        )
        final_cap = imdb_cap + "\n\n" + cap
    else:
        final_cap = cap
        
    sent_message = None
    if imdb and imdb.get('poster'):
        try:
            sent_message = await message.reply_photo(photo=imdb.get('poster'), caption=final_cap[:1024],
                                      reply_markup=btn, parse_mode=enums.ParseMode.MARKDOWN)
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            sent_message = await message.reply_photo(photo=poster, caption=final_cap[:1024], reply_markup=btn, parse_mode=enums.ParseMode.MARKDOWN)
        except Exception as e:
            logger.exception(e)
            sent_message = await message.reply_text(final_cap, reply_markup=btn, parse_mode=enums.ParseMode.MARKDOWN)
    else:
        sent_message = await message.reply_text(final_cap, reply_markup=btn, parse_mode=enums.ParseMode.MARKDOWN)

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
        not_found_text = (
            "**षमा करें, हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌**\n\n"
            "**Sorry, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊**\n"
            "_____________________\n\n"
            "**Search second bot - @asfilter_bot**"
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
                if match.groups():
                    gs_parsed.append(match.group(1))
                else:
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
            "**Sorry, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊**\n"
            "_____________________\n\n"
            "**Search second bot - @asfilter_bot**"
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
    btn.append([InlineKeyboardButton(text=to_fancy_font("Close"), callback_data=f'spolling#{user}#close_spellcheck')])
    spell_check_message = await msg.reply("I couldn't find anything relatd to that\nDid you mean any one of these?",
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
                            await message.reply_text(reply_text, disable_web_page_preview=True)
                        else:
                            button_structure = eval(btn)
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
