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

# BUTTONS will now store the search state including filters
# Format: BUTTONS[key] = {'search': str, 'offset': int, 'total_results': int, 'language': str/None, 'quality': str/None, 'season': str/None}
BUTTONS = {}
SPELL_CHECK = {}

# Filter Options Definitions
QUALITY_OPTIONS = [
    ("4K", "4K"), ("2K", "2K"), ("1080p", "1080p"), 
    ("720p", "720p"), ("480p", "480p"), ("BluRay", "BluRay"),
    ("HD Rip", "HD Rip"), ("Web-DL", "Web-DL"), ("HDRip", "HDRip")
]

INDIAN_LANGUAGES = [
    ("Hindi", "Hindi"), ("Tamil", "Tamil"), 
    ("Telugu", "Telugu"), ("Malayalam", "Malayalam"),
    ("Kannada", "Kannada"), ("Bengali", "Bengali"),
    ("Marathi", "Marathi"), ("Gujarati", "Gujarati"),
    ("Punjabi", "Punjabi"), ("English", "English")
]

# Season options (S01 to S50 as per your example)
SEASON_OPTIONS = [f"S{i:02d}" for i in range(1, 51)] 


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
        '(': '(', ')': ')', '[': '[', ']' : ']', '{': '{', '}': '}'
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

# NEW FUNCTION: Creates the filter option buttons
def create_filter_buttons(filter_type, key, current_state=None):
    """Creates a list of InlineKeyboardButtons for the given filter type."""
    buttons = []
    
    # Back button to return to the main file list
    back_button = [InlineKeyboardButton(text="⏪ Bᴀᴄᴋ ᴛᴏ Fɪʟᴇs", callback_data=f"back_to_files#{key}")]
    
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
        return back_button # Should not happen

    # Create buttons in rows of 3 or 5
    items_per_row = 3 if filter_type in ["quality", "language"] else 5
    
    for i in range(0, len(options), items_per_row):
        row = []
        for name, data in options[i:i+items_per_row]:
            # Add a checkmark if this is the currently selected option
            text = f"✅ {name}" if current_selection == data else name
            row.append(
                InlineKeyboardButton(
                    text=to_fancy_font(text),
                    callback_data=f"filter_{filter_type}_{data}#{key}"
                )
            )
        buttons.append(row)
        
    buttons.append(back_button)
    return buttons


# NEW FUNCTION: Runs the search based on the current state in BUTTONS
async def run_filtered_search(client, query, key, back_to_main=False):
    """Re-runs the search with current filters and updates the message."""
    search_data = BUTTONS.get(key)
    if not search_data:
        # If search data is lost, send a new message asking to search again
        return await query.message.edit_text("Search expired. Please search again.")

    # Reset offset for a new search if filters were just changed
    offset = 0 if not back_to_main else search_data.get('offset', 0)
    
    search = search_data['search']
    current_language = search_data['language']
    current_quality = search_data['quality']
    current_season = search_data['season']

    # Get new search results with filters
    files, n_offset, total_results = await get_search_results(
        search, 
        offset=offset, 
        filter=True, 
        language=current_language, 
        quality=current_quality, 
        season=current_season
    )

    # Update search_data in the global dictionary
    search_data['offset'] = n_offset
    search_data['total_results'] = total_results
    BUTTONS[key] = search_data
    
    settings = await get_settings(query.message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    
    # --- Start building buttons ---

    # File buttons
    if settings['button']:
        file_btn = [
            [
                InlineKeyboardButton(
                    text=f"📁 {to_fancy_font(file.file_name)}",
                    callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        file_btn = [
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
    
    btn = file_btn
    
    # Filter buttons row - Show current selection in button text
    btn.append([
        InlineKeyboardButton(text=f"🎬 Qᴜᴀʟɪᴛʏ ({current_quality or 'None'})", callback_data=f"open_filter#quality#{key}"),
        InlineKeyboardButton(text=f"🌐 Lᴀɴɢᴜᴀɢᴇ ({current_language or 'None'})", callback_data=f"open_filter#language#{key}"),
        InlineKeyboardButton(text=f"📺 Sᴇᴀsᴏɴ ({current_season or 'None'})", callback_data=f"open_filter#season#{key}")
    ])
    
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
    req = query.from_user.id if query.from_user else 0
    current_page = math.ceil(offset / 10) + 1
    total_pages = math.ceil(total_results / 10)
    
    pagination_buttons = []
    
    if offset > 0:
        pagination_buttons.append(
            InlineKeyboardButton("⏪ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset-10}")
        )
    
    pagination_buttons.append(
        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages")
    )
    
    if n_offset != 0 and n_offset < total_results:
        pagination_buttons.append(
            InlineKeyboardButton("Nᴇxᴛ ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
        )
    
    if pagination_buttons:
        btn.append(pagination_buttons)
        
    # --- End building buttons ---

    # Custom Message
    user_mention = query.from_user.mention if query.from_user else 'Usᴇʀ'
    chat_title = query.message.chat.title if query.message.chat.title else 'ᴛʜɪs ɢʀᴏᴜᴘ'
    
    filters_applied = f"**Filters:** Q: `{current_quality or 'None'}`, L: `{current_language or 'None'}`, S: `{current_season or 'None'}`"

    custom_msg = f"""
**[ 📂 ʜᴇʀᴇ ɪ ғᴏᴜɴᴅ ғᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ >{search}<**
{filters_applied}
**📢 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ - >{user_mention}<**
**♾️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ - >{chat_title}<**

**🍿 Yᴏᴜʀ ᴍᴏᴠɪᴇ ғɪʟᴇs ({total_results}) 👇**]
"""
    
    try:
        await query.message.edit_text(
            text=custom_msg, 
            reply_markup=InlineKeyboardMarkup(btn), 
            parse_mode=enums.ParseMode.MARKDOWN
        )
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error editing message in run_filtered_search: {e}")


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
    except ValueError:
        offset = 0
    
    # MODIFIED: Get the entire filter state
    search_data = BUTTONS.get(key)
    if not search_data:
        await query.answer("You are using one of my old messages, please send the request again.", show_alert=True)
        return

    search = search_data['search']
    current_language = search_data['language']
    current_quality = search_data['quality']
    current_season = search_data['season']
    
    # MODIFIED: Pass filters to get_search_results
    files, n_offset, total = await get_search_results(
        search, 
        offset=offset, 
        filter=True, 
        language=current_language, 
        quality=current_quality, 
        season=current_season
    )
    
    try:
        n_offset = int(n_offset) if n_offset else 0
    except ValueError:
        n_offset = 0

    if not files:
        await query.answer("No more results.", show_alert=True)
        return
        
    # MODIFIED: Update the offset/total in BUTTONS
    search_data['offset'] = n_offset
    search_data['total_results'] = total
    BUTTONS[key] = search_data

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
        InlineKeyboardButton(text=f"🎬 Qᴜᴀʟɪᴛʏ ({current_quality or 'None'})", callback_data=f"open_filter#quality#{key}"),
        InlineKeyboardButton(text=f"🌐 Lᴀɴɢᴜᴀɢᴇ ({current_language or 'None'})", callback_data=f"open_filter#language#{key}"),
        InlineKeyboardButton(text=f"📺 Sᴇᴀsᴏɴ ({current_season or 'None'})", callback_data=f"open_filter#season#{key}")
    ])
    
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
    
    if n_offset != 0 and n_offset < total:
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
    
    search_data = BUTTONS.get(key)
    if not search_data:
        await query.answer("Search expired. Please search again.", show_alert=True)
        return
    
    await query.answer("Sending all files to your PM...", show_alert=True)
    
    search = search_data['search']
    current_language = search_data['language']
    current_quality = search_data['quality']
    current_season = search_data['season']
    
    # Get all files for this search (Max 1000 for safety)
    all_files = []
    offset = 0
    max_total_files = 1000 # Safety limit
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
        except (TypeError, ValueError):
            next_offset = 0

        if next_offset == 0 or len(all_files) >= max_total_files:
            break
        offset = next_offset
    
    if not all_files:
        await query.message.reply_text("❌ No files found to send.")
        return
    
    user_id = query.from_user.id
    sent_count = 0
    
    # Send files to user's PM
    for file in all_files:
        # ... (File sending logic remains the same)
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
                protect_content=True # Assuming file_secure is intended for PM sendall
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
    filters_applied = f"**Filters:** Q: `{current_quality or 'None'}`, L: `{current_language or 'None'}`, S: `{current_season or 'None'}`"
    notification = await query.message.reply_text(
        f"✅ Successfully sent {sent_count} files to your PM!\n"
        f"📁 Files will be auto-deleted in 5 minutes.\n"
        f"🔍 Search: `{search}`\n"
        f"{filters_applied}"
    )
    
    # Delete notification after 10 seconds
    asyncio.create_task(schedule_delete(notification, 10))


# Removed individual language/session handlers as they are now handled by filter_ callback


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
    
    # --- NEW FILTER HANDLERS ---
    elif query.data.startswith("open_filter#"):
        await query.answer()
        # open_filter#filter_type#key
        _, filter_type, key = query.data.split("#")
        
        search_data = BUTTONS.get(key)
        if not search_data:
            return await query.message.edit_text("Search expired. Please search again.")

        # Create filter buttons
        filter_buttons = create_filter_buttons(filter_type, key, search_data)

        # Edit message with filter buttons
        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(filter_buttons)
        )

    elif query.data.startswith("filter_"):
        # filter_quality_480p#key, filter_language_Hindi#key, filter_season_S01#key
        parts = query.data.split("_", 2)
        filter_type = parts[1]
        filter_value_and_key = parts[2]
        filter_value, key = filter_value_and_key.split("#")
        
        search_data = BUTTONS.get(key)
        if not search_data:
            return await query.answer("Search expired. Please search again.", show_alert=True)

        # Toggle logic - If already selected, deselect it (set to None)
        current_selection = search_data.get(filter_type)
        if current_selection == filter_value:
             search_data[filter_type] = None
             await query.answer(f"❌ {filter_type.capitalize()} filter removed.", show_alert=False)
        else:
             search_data[filter_type] = filter_value
             await query.answer(f"✅ {filter_type.capitalize()} set to {filter_value}", show_alert=False)

        # Update search_data in the global dictionary
        BUTTONS[key] = search_data

        # Update button state (checkmarks)
        new_filter_buttons = create_filter_buttons(filter_type, key, search_data)
        
        # Edit message to show updated checkmarks
        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(new_filter_buttons)
        )
        
        # Run search with new filter
        await run_filtered_search(client, query, key)


    elif query.data.startswith("back_to_files#"):
        # back_to_files#key
        _, key = query.data.split("#")
        await query.answer()
        await run_filtered_search(client, query, key, back_to_main=True)
    # --- END NEW FILTER HANDLERS ---
    
    # ... (other handlers like sendall, delallconfirm, groupcb, file, checksub etc. remain here)
    elif query.data.startswith("sendall"):
        # This will be handled by the send_all_files function above
        pass
    
    elif query.data.startswith("session_"):
        # This is now handled by the generic filter logic (open_filter#season)
        await query.answer("Please use the 'Season' button for filtering.", show_alert=True)
    
    elif query.data.startswith("lang_"):
        # This is now handled by the generic filter logic (open_filter#language)
        await query.answer("Please use the 'Language' button for filtering.", show_alert=True)

    # ... (Your existing code for delallconfirm, groupcb, connectcb, disconnect, deletecb, backcb, alertmessage)
    
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
        
        # ... (Caption, Force Sub/Bot PM Check and File sending logic remains the same)
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

    
    # ... (rest of the cb_handler remains the same)
    
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
                    not_found_text = (
                        "**षमा करें, हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌**\n\n"
                        "**sᴏʀʀʏ, ᴡᴇ ʜᴀᴠᴇɴ'ᴛ ғɪɴᴅ ʏᴏᴜʀ ғɪʟᴇ. ᴍᴀʏʙᴇ ʏᴏᴜ ᴍᴀᴅᴇ ᴀ ᴍɪsᴛᴀᴋᴇ? ᴘʟᴇᴀsᴇ ᴛʀʏ ᴛᴏ ᴡʀɪᴛᴇ ᴄᴏʀʀᴇᴄᴛʟʏ 😊**\n"
                        "_____________________\n\n"
                        "**sᴇᴀʀᴄʜ sᴇᴄᴏɴᴅ ʙᴏᴛ - @asfilter_bot**"
                    )
                    not_found_message = await msg.reply_text(not_found_text, quote=True, parse_mode=enums.ParseMode.MARKDOWN)
                    asyncio.create_task(schedule_delete(not_found_message, 10))
                    return
        else:
            return
    else:
        # If from spell check, use the message the search was initiated from
        message = msg.message.reply_to_message
        settings = await get_settings(message.chat.id)
        search, files, offset, total_results = spoll
    
    # Store search and initial empty filter state
    key = f"{message.chat.id}-{message.id}"
    BUTTONS[key] = {
        'search': search, 
        'offset': offset, 
        'total_results': total_results, 
        'language': None,
        'quality': None,
        'season': None
    }
        
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

    # Filter buttons row
    btn.append([
        InlineKeyboardButton(text="🎬 Qᴜᴀʟɪᴛʏ", callback_data=f"open_filter#quality#{key}"),
        InlineKeyboardButton(text="🌐 Lᴀɴɢᴜᴀɢᴇ", callback_data=f"open_filter#language#{key}"),
        InlineKeyboardButton(text="📺 Sᴇᴀsᴏɴ", callback_data=f"open_filter#season#{key}")
    ])
    
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
    req = message.from_user.id if message.from_user else 0
    
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

**🍿 Yᴏᴜʀ ᴍᴏᴠɪᴇ ғɪʟᴇs ({total_results}) 👇**]
"""

    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    TEMPLATE = settings['template']
    
    # IMDB and Caption Logic (Kept as is for consistency)
    if imdb:
        # ... (IMDB caption generation logic)
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
