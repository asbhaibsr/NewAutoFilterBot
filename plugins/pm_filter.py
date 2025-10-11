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


# Enhanced fancy font converter - Simplified for clean buttons, no emojis
def to_fancy_font(text):
    """Converts text to fancy font style, avoiding emojis for clean buttons"""
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
        '✅': '✅', '❌': '❌' # Keep checkmarks as they are
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
    back_button = [InlineKeyboardButton(text=to_fancy_font("⏪ Back To Files"), callback_data=f"back_to_files#{key}")]
    
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
            # Add a checkmark if this is the currently selected option - FIX FOR TICK MARK
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
        return await query.message.edit_text(to_fancy_font("Search expired. Please search again."))

    # Reset offset for a new search if filters were just changed, otherwise use stored offset
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
    btn = []
    
    # Filter buttons row (New Order: Quality, Language, Season - above Send All)
    btn.append([
        InlineKeyboardButton(text=to_fancy_font(f"🎬 Quality ({current_quality or 'None'})"), callback_data=f"open_filter#quality#{key}"),
        InlineKeyboardButton(text=to_fancy_font(f"🌐 Language ({current_language or 'None'})"), callback_data=f"open_filter#language#{key}"),
        InlineKeyboardButton(text=to_fancy_font(f"📺 Season ({current_season or 'None'})"), callback_data=f"open_filter#season#{key}")
    ])
    
    # Send All Files button
    btn.append([
        InlineKeyboardButton(
            text=to_fancy_font("🚀 Send All Files"), 
            callback_data=f"sendall_{key}"
        )
    ])
    
    # File buttons
    if settings['button']:
        file_btn = [
            [
                InlineKeyboardButton(
                    # APPLY FANCY FONT TO FILE NAME
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
                    # APPLY FANCY FONT TO FILE NAME
                    text=f"📂 {to_fancy_font(file.file_name)}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
                InlineKeyboardButton(
                    # APPLY FANCY FONT TO FILE SIZE
                    text=f"💾 {to_fancy_font(get_size(file.file_size))}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
            ]
            for file in files
        ]
    
    btn.extend(file_btn)
    
    # Pagination
    req = query.from_user.id if query.from_user else 0
    current_page = math.ceil(offset / 10) + 1
    total_pages = math.ceil(total_results / 10)
    
    pagination_buttons = []
    
    if offset > 0:
        pagination_buttons.append(
            InlineKeyboardButton(to_fancy_font("⏪ Back"), callback_data=f"next_{req}_{key}_{offset-10}")
        )
    
    pagination_buttons.append(
        InlineKeyboardButton(to_fancy_font(f"📄 {current_page}/{total_pages}"), callback_data="pages")
    )
    
    if n_offset != 0 and n_offset < total_results:
        pagination_buttons.append(
            InlineKeyboardButton(to_fancy_font("Next ⏩"), callback_data=f"next_{req}_{key}_{n_offset}")
        )
    
    if pagination_buttons:
        btn.append(pagination_buttons)
        
    # Check Bot PM button (FIX: Direct user mention, no link)
    btn.append([
        InlineKeyboardButton(
            text=to_fancy_font("🔍 Check Bot PM"), 
            url=f"https://t.me/{temp.U_NAME}" # Correct URL for PM
        )
    ])
        
    # --- End building buttons ---

    # Custom Message - FIX: Removed ([), (]), and (<>) from search result message
    user_mention = query.from_user.mention if query.from_user else 'User'
    chat_title = query.message.chat.title if query.message.chat.title else 'This Group'
    
    filters_applied = f"**Filters:** Q: `{current_quality or 'None'}`, L: `{current_language or 'None'}`, S: `{current_season or 'None'}`"
    
    # Cleaned up message format as requested
    # FIX: Requested by message structure changed to avoid fancy font link error
    custom_msg = f"""
**📂 Here I Found For Your Search: {search.replace('<', '').replace('>', '').strip()}**
{filters_applied}

**📢 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:** {user_mention}
**♾️ Powered By: {chat_title}**

**🍿 Your Movie Files ({total_results}) 👇**
"""
    
    try:
        await query.message.edit_text(
            text=to_fancy_font(custom_msg), 
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
    
    btn = []
    
    # Filter buttons row (New Order)
    btn.append([
        InlineKeyboardButton(text=to_fancy_font(f"🎬 Quality ({current_quality or 'None'})"), callback_data=f"open_filter#quality#{key}"),
        InlineKeyboardButton(text=to_fancy_font(f"🌐 Language ({current_language or 'None'})"), callback_data=f"open_filter#language#{key}"),
        InlineKeyboardButton(text=to_fancy_font(f"📺 Season ({current_season or 'None'})"), callback_data=f"open_filter#season#{key}")
    ])
    
    # Send All Files button
    btn.append([
        InlineKeyboardButton(
            text=to_fancy_font("🚀 Send All Files"), 
            callback_data=f"sendall_{key}"
        )
    ])
    
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
        
    btn.extend(file_btn)


    # Pagination
    current_page = math.ceil(offset / 10) + 1
    total_pages = math.ceil(total / 10)
    
    pagination_buttons = []
    if offset > 0:
        pagination_buttons.append(
            InlineKeyboardButton(to_fancy_font("⏪ Back"), callback_data=f"next_{req}_{key}_{offset-10}")
        )
    
    pagination_buttons.append(
        InlineKeyboardButton(to_fancy_font(f"📄 {current_page}/{total_pages}"), callback_data="pages")
    )
    
    if n_offset != 0 and n_offset < total:
        pagination_buttons.append(
            InlineKeyboardButton(to_fancy_font("Next ⏩"), callback_data=f"next_{req}_{key}_{n_offset}")
        )
    
    if pagination_buttons:
        btn.append(pagination_buttons)
        
    # Check Bot PM button (FIX: Direct user mention, no link)
    btn.append([
        InlineKeyboardButton(
            text=to_fancy_font("🔍 Check Bot PM"), 
            url=f"https://t.me/{temp.U_NAME}"
        )
    ])

    try:
        # Re-fetch the custom message logic here to ensure it updates with new filters/pagination
        user_mention = query.from_user.mention if query.from_user else 'User'
        chat_title = query.message.chat.title if query.message.chat.title else 'This Group'
        filters_applied = f"**Filters:** Q: `{current_quality or 'None'}`, L: `{current_language or 'None'}`, S: `{current_season or 'None'}`"
        custom_msg = f"""
**📂 Here I Found For Your Search: {search.replace('<', '').replace('>', '').strip()}**
{filters_applied}

**📢 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:** {user_mention}
**♾️ Powered By: {chat_title}**

**🍿 Your Movie Files ({total}) 👇**
"""
        
        await query.message.edit_text(
            text=to_fancy_font(custom_msg), 
            reply_markup=InlineKeyboardMarkup(btn), 
            parse_mode=enums.ParseMode.MARKDOWN
        )

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
        notification = await query.message.reply_text(to_fancy_font("❌ No files found to send with the current filters."))
        asyncio.create_task(schedule_delete(notification, 10))
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
            # IMPORTANT: Using client.send_cached_media ensures file is sent via bot, not just a forwarded message
            sent_msg = await bot.send_cached_media(
                chat_id=user_id,
                file_id=file.file_id,
                caption=file_caption,
                # Assume if sendall is used, file_secure logic should apply here too
                protect_content=True 
            )
            
            sent_count += 1
            
            # Schedule deletion after 5 minutes
            asyncio.create_task(schedule_delete(sent_msg, 300))
            
            # Small delay to avoid flooding
            await asyncio.sleep(0.5)
            
        except UserIsBlocked:
            await query.message.reply_text(to_fancy_font("❌ Please unblock the bot first!"))
            return
        except PeerIdInvalid:
             await query.message.reply_text(to_fancy_font("❌ Please start the bot in private chat first!"), 
                                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_fancy_font("▶️ Start Bot"), url=f"https://t.me/{temp.U_NAME}")]])
                                           )
             return
        except Exception as e:
            logger.error(f"Error sending file {file.file_name}: {e}")
            continue
    
    # Notification
    filters_applied = f"**Filters:** Q: `{current_quality or 'None'}`, L: `{current_language or 'None'}`, S: `{current_season or 'None'}`"
    notification = await query.message.reply_text(
        to_fancy_font(f"✅ Successfully sent {sent_count} files to your PM!\n"
        f"📁 Files will be auto-deleted in 5 minutes.\n"
        f"🔍 Search: `{search}`\n"
        f"{filters_applied}")
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
        return await query.answer(to_fancy_font("You are clicking on an old button which is expired."), show_alert=True)
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
            k = await query.message.edit(to_fancy_font('This Movie Not Found In DataBase'))
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
            return await query.message.edit_text(to_fancy_font("Search expired. Please search again."))

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
            return await query.answer(to_fancy_font("Search expired. Please search again."), show_alert=True)

        # Toggle logic - If already selected, deselect it (set to None)
        current_selection = search_data.get(filter_type)
        
        # Check if the selection results in a file
        temp_search = search_data['search']
        temp_lang = search_data['language']
        temp_quality = search_data['quality']
        temp_season = search_data['season']
        
        new_value = None # Default is removal
        alert_msg = ""
        
        if current_selection == filter_value:
             new_value = None # Remove filter
             alert_msg = f"❌ {filter_type.capitalize()} filter removed."
        else:
             # Check if this new filter combination yields results
             if filter_type == 'quality': temp_quality = filter_value
             elif filter_type == 'language': temp_lang = filter_value
             elif filter_type == 'season': temp_season = filter_value

             # Search with new filters, offset 0, max_results 1 (just to check existence)
             files_check, _, _ = await get_search_results(
                 temp_search, offset=0, max_results=1, 
                 language=temp_lang, quality=temp_quality, season=temp_season
             )
             
             if not files_check:
                 # If no files found, don't set the filter and inform user
                 alert_msg = f"🚫 No file found for {filter_value} filter. Please choose another."
                 await query.answer(to_fancy_font(alert_msg), show_alert=True)
                 # Update button state (checkmarks) to show it's NOT selected
                 new_filter_buttons = create_filter_buttons(filter_type, key, search_data)
                 await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_filter_buttons))
                 return # Exit without running search

             # If files are found, set the new filter value
             new_value = filter_value
             alert_msg = f"✅ {filter_type.capitalize()} set to {filter_value}"
        
        # Update the state
        search_data[filter_type] = new_value
        await query.answer(to_fancy_font(alert_msg), show_alert=False)

        # Update search_data in the global dictionary
        BUTTONS[key] = search_data

        # Update button state (checkmarks)
        new_filter_buttons = create_filter_buttons(filter_type, key, search_data)
        
        # Edit message to show updated checkmarks
        try:
             await query.message.edit_reply_markup(
                 reply_markup=InlineKeyboardMarkup(new_filter_buttons)
             )
        except MessageNotModified:
             pass
        
        # Run search with new filter
        await run_filtered_search(client, query, key)


    elif query.data.startswith("back_to_files#"):
        # back_to_files#key
        _, key = query.data.split("#")
        await query.answer()
        await run_filtered_search(client, query, key, back_to_main=True)
    # --- END NEW FILTER HANDLERS ---
    
    elif query.data.startswith("sendall"):
        # This will be handled by the send_all_files function above
        pass
    
    # Removed explicit lang/season/quality handlers as they use the generic logic
    
    # PM ISSUE FIX & File Sent Message Logic
    elif query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        
        # FIX FOR KeyError: 0
        if not files_:
            # This check handles the error you were seeing in the logs if get_file_details returns empty
            return await query.answer(to_fancy_font('No Such File Exist.'))
        
        files = files_[0] # Safely access the first item now
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
                # Use protect_content only if file_secure is enabled
                protect_content=True if ident == "filep" else False 
            )
            
            # Warning message (kept the original Hindi/English text)
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
            await query.answer(to_fancy_font('Check PM, I have sent the file. It will be deleted in 5 minutes.'), show_alert=True)
            
        except UserIsBlocked:
            await query.answer(to_fancy_font('Unblock the bot first!'), show_alert=True)
        except PeerIdInvalid:
            # User hasn't started the bot yet. Redirect them to start it.
            await query.answer(to_fancy_font("Please start the bot in private chat first!"), url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}", show_alert=True)
        except Exception as e:
            # Catch all other errors and redirect to PM as a fallback
            logger.exception(f"Error sending file to PM: {e}")
            await query.answer(to_fancy_font("An error occurred while sending the file. Please try again later or contact admin."), show_alert=True)
            # Fallback to start link might still be useful in some unknown edge cases
            # await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}") 

    # ... (rest of the cb_handler remains the same)
    
    elif query.data.startswith("checksub"):
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer("ɪ ʟɪᴋᴇ ʏᴏᴜʀ sᴍᴀʀᴛɴᴇss, ʙᴜᴛ ᴅᴏɴ'T ʙᴇ ᴏᴠᴇʀsᴍᴀʀᴛ 😒", show_alert=True)
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
            InlineKeyboardButton(to_fancy_font('➕ Add Me To Your Groups ➕'), url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ], [
            InlineKeyboardButton(to_fancy_font('🔍 Search'), switch_inline_query_current_chat=''),
            InlineKeyboardButton(to_fancy_font('🤖 Updates'), url='https://t.me/asbhai_bsr')
        ], [
            InlineKeyboardButton(to_fancy_font('ℹ️ Help'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('😊 About'), callback_data='about')
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
            InlineKeyboardButton(to_fancy_font('Manual Filter'), callback_data='manuelfilter'),
            InlineKeyboardButton(to_fancy_font('Auto Filter'), callback_data='autofilter')
        ], [
            InlineKeyboardButton(to_fancy_font('Connection'), callback_data='coct'),
            InlineKeyboardButton(to_fancy_font('Extra Mods'), callback_data='extra')
        ], [
            InlineKeyboardButton(to_fancy_font('🏠 Home'), callback_data='start'),
            InlineKeyboardButton(to_fancy_font('🔮 Status'), callback_data='stats')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.HELP_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "about":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('🤖 Updates'), url='https://t.me/asbhai_bsr'),
            InlineKeyboardButton(to_fancy_font('♥️ Source'), callback_data='source')
        ], [
            InlineKeyboardButton(to_fancy_font('🏠 Home'), callback_data='start'),
            InlineKeyboardButton(to_fancy_font('🔐 Close'), callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "source":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 Back'), callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.SOURCE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "manuelfilter":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 Back'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('⏹️ Buttons'), callback_data='button')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.MANUELFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "button":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 Back'), callback_data='manuelfilter')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.BUTTON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "autofilter":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 Back'), callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.AUTOFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "coct":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 Back'), callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CONNECTION_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "extra":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 Back'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('👮‍♂️ Admin'), callback_data='admin')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.EXTRAMOD_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "admin":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 Back'), callback_data='extra')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ADMIN_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "stats":
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 Back'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('♻️ Refresh'), callback_data='rfrsh')
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
        await query.answer("Fetching MongoDB Database")
        buttons = [[
            InlineKeyboardButton(to_fancy_font('👩‍🦯 Back'), callback_data='help'),
            InlineKeyboardButton(to_fancy_font('♻️ Refresh'), callback_data='rfrsh')
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
            await query.message.edit(to_fancy_font("Your active connection has been changed. Go to /settings."))
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
                    InlineKeyboardButton(to_fancy_font('Filter Button'),
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('Single') if settings["button"] else to_fancy_font('Double'),
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('Bot PM'), callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ Yes') if settings["botpm"] else to_fancy_font('❌ No'),
                                         callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('File Secure'),
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ Yes') if settings["file_secure"] else to_fancy_font('❌ No'),
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('IMDB'), callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ Yes') if settings["imdb"] else to_fancy_font('❌ No'),
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('Spell Check'),
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ Yes') if settings["spell_check"] else to_fancy_font('❌ No'),
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton(to_fancy_font('Welcome'), callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton(to_fancy_font('✅ Yes') if settings["welcome"] else to_fancy_font('❌ No'),
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
                        "**Sorry, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊**\n"
                        "_____________________\n\n"
                        "**Search second bot - @asfilter_bot**"
                    )
                    # APPLY FANCY FONT TO NOT FOUND MESSAGE
                    not_found_message = await msg.reply_text(to_fancy_font(not_found_text), quote=True, parse_mode=enums.ParseMode.MARKDOWN)
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
    btn = []

    # Filter buttons row (New Order: Quality, Language, Season - above Send All)
    btn.append([
        InlineKeyboardButton(text=to_fancy_font("🎬 Quality"), callback_data=f"open_filter#quality#{key}"),
        InlineKeyboardButton(text=to_fancy_font("🌐 Language"), callback_data=f"open_filter#language#{key}"),
        InlineKeyboardButton(text=to_fancy_font("📺 Season"), callback_data=f"open_filter#season#{key}")
    ])
    
    # Send All Files button
    btn.append([
        InlineKeyboardButton(
            text=to_fancy_font("🚀 Send All Files"), 
            callback_data=f"sendall_{key}"
        )
    ])
    
    # File buttons
    if settings["button"]:
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
        
    btn.extend(file_btn)

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
            InlineKeyboardButton(to_fancy_font("⏪ Back"), callback_data=f"next_{req}_{key}_{int_offset-10}")
        )
    
    pagination_buttons.append(
        InlineKeyboardButton(to_fancy_font(f"📄 {current_page}/{total_pages}"), callback_data="pages")
    )
    
    if int_offset + 10 < total_results:
        pagination_buttons.append(
            InlineKeyboardButton(to_fancy_font("Next ⏩"), callback_data=f"next_{req}_{key}_{int_offset+10}")
        )
    
    if pagination_buttons:
        btn.append(pagination_buttons)

    # Check Bot PM button (FIX: Direct user mention, no link)
    btn.append([
        InlineKeyboardButton(
            text=to_fancy_font("🔍 Check Bot PM"), 
            url=f"https://t.me/{temp.U_NAME}"
        )
    ])

    # Custom Message - FIX: Removed ([), (]), and (<>) from search result message
    user_mention = message.from_user.mention if message.from_user else 'User'
    chat_title = message.chat.title if message.chat.title else 'This Group'
    
    # FIX: Requested by message structure changed to avoid fancy font link error
    custom_msg = f"""
**📂 Here I Found For Your Search: {search.replace('<', '').replace('>', '').strip()}**

**📢 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:** {user_mention}
**♾️ Powered By: {chat_title}**

**🍿 Your Movie Files ({total_results}) 👇**
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
            # Apply fancy font to the final caption
            sent_message = await message.reply_photo(photo=imdb.get('poster'), caption=to_fancy_font(cap[:1024]),
                                      reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.MARKDOWN)
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            # Apply fancy font to the final caption
            sent_message = await message.reply_photo(photo=poster, caption=to_fancy_font(cap[:1024]), reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.MARKDOWN)
        except Exception as e:
            logger.exception(e)
            # Apply fancy font to the final caption
            sent_message = await message.reply_text(to_fancy_font(cap), reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.MARKDOWN)
    else:
        # Apply fancy font to the final caption
        sent_message = await message.reply_text(to_fancy_font(cap), reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.MARKDOWN)

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
            "**Sorry, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊**\n"
            "_____________________\n\n"
            "**Search second bot - @asfilter_bot**"
        )
        k = await msg.reply_text(to_fancy_font(not_found_text), parse_mode=enums.ParseMode.MARKDOWN)
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
            "**Sorry, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊**\n"
            "_____________________\n\n"
            "**Search second bot - @asfilter_bot**"
        )
        k = await msg.reply_text(to_fancy_font(not_found_text), parse_mode=enums.ParseMode.MARKDOWN)
        asyncio.create_task(schedule_delete(k, 8))
        return
    SPELL_CHECK[msg.id] = movielist
    btn = [[
        InlineKeyboardButton(
            text=to_fancy_font(movie.strip()),
            callback_data=f"spolling#{user}#{k}",
        )
    ] for k, movie in enumerate(movielist)]
    btn.append([InlineKeyboardButton(text=to_fancy_font("🔐 Close"), callback_data=f'spolling#{user}#close_spellcheck')])
    spell_check_message = await msg.reply(to_fancy_font("I couldn't find anything relatd to that\nDid you mean any one of these?"),
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
                # Apply fancy font to reply text
                reply_text = to_fancy_font(reply_text) 

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
