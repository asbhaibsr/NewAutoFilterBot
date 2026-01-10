import os
import re
import logging
import asyncio
import random
import string
import time
import math
from datetime import datetime, timedelta
from typing import Union, Optional, Dict, List
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    Message, 
    CallbackQuery,
    InputMediaPhoto,
    InputMediaDocument
)
from pyrogram.errors import (
    FloodWait, 
    UserIsBlocked, 
    InputUserDeactivated,
    PeerIdInvalid,
    ChatAdminRequired
)
from database.ia_filterdb import (
    Media, 
    get_file_details, 
    get_search_results, 
    get_bad_files,
    delete_files
)
from database.users_chats_db import db
from info import *
from utils import (
    get_size, 
    is_subscribed, 
    get_poster, 
    search_gagala, 
    temp, 
    get_settings,
    save_group_settings
)
from database.connections_mdb import active_connection
import humanize
from Script import script
from plugins.filters import Filter
from plugins.gfilters import GFilters
from plugins.pm_filter import PM_Filter
from plugins.commands import Commands
from plugins.routes import Routes
from plugins.auto_delete import AutoDelete
import json
import base64
import pytz

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BUTTONS = {}
SPELL_CHECK = {}

# Auto-delete function
async def delete_messages_after_delay(bot_msg, user_msg=None, delay=300, delete_user=True):
    """
    Delete messages after specified delay
    delay: seconds
    delete_user: True to delete user message, False to keep it
    """
    try:
        await asyncio.sleep(delay)
        
        # Delete bot message
        try:
            await bot_msg.delete()
        except Exception as e:
            logger.error(f"Error deleting bot message: {e}")
        
        # Delete user message if required
        if delete_user and user_msg:
            try:
                await user_msg.delete()
            except Exception as e:
                logger.error(f"Error deleting user message: {e}")
                
    except Exception as e:
        logger.error(f"Error in delete_messages_after_delay: {e}")

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    k = await manual_filters(client, message)
    if k == False:
        await auto_filter(client, message)

# Main auto_filter function with auto-delete
@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) != 0 and query.from_user.id != int(req):
        return await query.answer("This is not for you!", show_alert=True)
    
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
    if settings['button']:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[{get_size(file.file_size)}] {file.file_name}", 
                    callback_data=f'file#{file.file_id}'
                )
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{file.file_name}",
                    callback_data=f'file#{file.file_id}'
                ),
                InlineKeyboardButton(
                    text=f"{get_size(file.file_size)}",
                    callback_data=f'file_#{file.file_id}',
                )
            ]
            for file in files
        ]

    btn.insert(0, 
        [
            InlineKeyboardButton("🤖 Check PM", url=f"https://t.me/{BOT_PM_USERNAME}")
        ]
    )
    
    if 0 < offset <= 10:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - 10
    
    if n_offset == 0:
        btn.append(
            [InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
             InlineKeyboardButton(f"📃 {math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", 
                                 callback_data="pages")]
        )
    elif off_set is None:
        btn.append(
            [InlineKeyboardButton(f"🗓 {math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", 
                                 callback_data="pages"),
             InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")]
        )
    else:
        btn.append(
            [
                InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
            ]
        )
    
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except:
        pass
    await query.answer()

@Client.on_callback_query(filters.regex(r"^spolling"))
async def advantage_spoll_choker(bot, query):
    _, user, movie_ = query.data.split('#')
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer("This is not for you!", show_alert=True)
    
    if movie_ == "close_spellcheck":
        return await query.message.delete()
    
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer("You are clicking on an old button which is expired.", show_alert=True)
    
    movie = movies[int(movie_)]
    await query.message.delete()
    
    # Store search for auto-delete
    search = movie.strip()
    files, offset, total_results = await get_search_results(search.lower(), offset=0, filter=True)
    
    if not files:
        # Not found case - only delete bot message after 2 mins
        not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot - @asfilter_bot
"""
        k = await query.message.reply_to_message.reply(not_found_msg)
        # Auto delete only bot message, keep user message
        asyncio.create_task(delete_messages_after_delay(k, query.message.reply_to_message, 120, delete_user=False))
        return
    
    # Files found case
    settings = await get_settings(query.message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    
    if settings['button']:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[{get_size(file.file_size)}] {file.file_name}", 
                    callback_data=f'{pre}#{file.file_id}'
                )
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{file.file_name}",
                    callback_data=f'{pre}#{file.file_id}'
                ),
                InlineKeyboardButton(
                    text=f"{get_size(file.file_size)}",
                    callback_data=f'{pre}_#{file.file_id}',
                )
            ]
            for file in files
        ]
    
    btn.insert(0, 
        [
            InlineKeyboardButton("🤖 Check PM", url=f"https://t.me/{BOT_PM_USERNAME}")
        ]
    )
    
    if offset != "":
        key = f"{query.message.chat.id}-{query.message.id}"
        BUTTONS[key] = search
        req = query.from_user.id if query.from_user else 0
        btn.append(
            [
                InlineKeyboardButton(text=f"📃 1/{math.ceil(int(total_results)/10)}", callback_data="pages"),
                InlineKeyboardButton(text="NEXT ⏩", callback_data=f"next_{req}_{key}_{offset}")
            ]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="📃 1/1", callback_data="pages")]
        )
    
    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    
    try:
        req_by = query.from_user.mention
    except:
        req_by = "User"
    
    group_title = query.message.chat.title if query.message.chat.title else "Group"
    
    custom_caption = f"📂 ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ - **{search}**\n\n📢 ʀᴇǫᴜᴇꜱᴛᴇᴅ ʙʏ - {req_by}\n♾️ ᴘᴏᴡᴇᴇᴅ ʙʏ - {group_title}\n\n🍿 Your Movie Files 👇"
    
    TEMPLATE = settings.get('template', IMDB_TEMPLATE)
    
    if imdb:
        cap = custom_caption + "\n" + TEMPLATE.format(
            query=search, 
            title=imdb.get('title'),
            votes=imdb.get('votes'),
            aka=imdb.get("aka"),
            seasons=imdb.get("seasons"),
            box_office=imdb.get('box_office'),
            localized_title=imdb.get('localized_title'),
            kind=imdb.get('kind'),
            imdb_id=imdb.get("imdb_id"),
            cast=imdb.get("cast"),
            runtime=imdb.get("runtime"),
            countries=imdb.get("countries"),
            certificates=imdb.get("certificates"),
            languages=imdb.get("languages"),
            director=imdb.get("director"),
            writer=imdb.get("writer"),
            producer=imdb.get("producer"),
            composer=imdb.get("composer"),
            cinematographer=imdb.get("cinematographer"),
            music_team=imdb.get("music_team"),
            distributors=imdb.get("distributors"),
            release_date=imdb.get('release_date'),
            year=imdb.get('year'),
            genres=imdb.get('genres'),
            poster=imdb.get('poster'),
            plot=imdb.get('plot'),
            rating=imdb.get('rating'),
            url=imdb.get('url'),
            **locals()
        )
    else:
        cap = custom_caption
    
    # Send result
    try:
        if imdb and imdb.get('poster'):
            try:
                result_msg = await query.message.reply_to_message.reply_photo(
                    photo=imdb.get('poster'),
                    caption=cap[:1024],
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except:
                result_msg = await query.message.reply_to_message.reply_text(
                    cap,
                    reply_markup=InlineKeyboardMarkup(btn)
                )
        else:
            result_msg = await query.message.reply_to_message.reply_text(
                cap,
                reply_markup=InlineKeyboardMarkup(btn)
            )
        
        # Auto delete both messages after 5 minutes
        asyncio.create_task(delete_messages_after_delay(result_msg, query.message.reply_to_message, 300))
        
    except Exception as e:
        logger.exception(e)
        await query.message.reply_to_message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))

async def auto_filter(client, msg, spoll=False):
    if not spoll:
        message = msg
        settings = await get_settings(message.chat.id)
        
        if message.text.startswith("/"): 
            return  
        
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        
        if 2 < len(message.text) < 100:
            search = message.text
            files, offset, total_results = await get_search_results(search.lower(), offset=0, filter=True)
            
            not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot - @asfilter_bot
"""
            
            if not files:
                if settings["spell_check"]:
                    return await advantage_spell_chok(msg)
                else:
                    # Not found - delete only bot message after 2 minutes
                    k = await msg.reply(not_found_msg)
                    asyncio.create_task(delete_messages_after_delay(k, message, 120, delete_user=False))
                    return
        else:
            return
    else:
        settings = await get_settings(message.chat.id)
        message = msg.message.reply_to_message
        search, files, offset, total_results = spoll
    
    pre = 'filep' if settings['file_secure'] else 'file'
    
    if settings['button']:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[{get_size(file.file_size)}] {file.file_name}", 
                    callback_data=f'{pre}#{file.file_id}'
                )
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{file.file_name}",
                    callback_data=f'{pre}#{file.file_id}'
                ),
                InlineKeyboardButton(
                    text=f"{get_size(file.file_size)}",
                    callback_data=f'{pre}#{file.file_id}',
                )
            ]
            for file in files
        ]
    
    btn.insert(0, 
        [
            InlineKeyboardButton("🤖 Check PM", url=f"https://t.me/{BOT_PM_USERNAME}")
        ]
    )
    
    if offset != "":
        key = f"{message.chat.id}-{message.id}"
        BUTTONS[key] = search
        req = message.from_user.id if message.from_user else 0
        btn.append(
            [
                InlineKeyboardButton(text=f"📃 1/{math.ceil(int(total_results)/10)}", callback_data="pages"),
                InlineKeyboardButton(text="NEXT ⏩", callback_data=f"next_{req}_{key}_{offset}")
            ]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="📃 1/1", callback_data="pages")]
        )
    
    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    
    try:
        req_by = message.from_user.mention
    except:
        req_by = "User"
    
    group_title = message.chat.title if message.chat.title else "Group"
    
    custom_caption = f"📂 ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ - **{search}**\n\n📢 ʀᴇǫᴜᴇꜱᴛᴇᴅ ʙʏ - {req_by}\n♾️ ᴘᴏᴡᴇᴇᴅ ʙʏ - {group_title}\n\n🍿 Your Movie Files 👇"
    
    TEMPLATE = settings.get('template', IMDB_TEMPLATE)
    
    if imdb:
        cap = custom_caption + "\n" + TEMPLATE.format(
            query=search, 
            title=imdb.get('title'),
            votes=imdb.get('votes'),
            aka=imdb.get("aka"),
            seasons=imdb.get("seasons"),
            box_office=imdb.get('box_office'),
            localized_title=imdb.get('localized_title'),
            kind=imdb.get('kind'),
            imdb_id=imdb.get("imdb_id"),
            cast=imdb.get("cast"),
            runtime=imdb.get("runtime"),
            countries=imdb.get("countries"),
            certificates=imdb.get("certificates"),
            languages=imdb.get("languages"),
            director=imdb.get("director"),
            writer=imdb.get("writer"),
            producer=imdb.get("producer"),
            composer=imdb.get("composer"),
            cinematographer=imdb.get("cinematographer"),
            music_team=imdb.get("music_team"),
            distributors=imdb.get("distributors"),
            release_date=imdb.get('release_date'),
            year=imdb.get('year'),
            genres=imdb.get('genres'),
            poster=imdb.get('poster'),
            plot=imdb.get('plot'),
            rating=imdb.get('rating'),
            url=imdb.get('url'),
            **locals()
        )
    else:
        cap = custom_caption
    
    # Send result with auto-delete
    try:
        if imdb and imdb.get('poster'):
            try:
                result_msg = await message.reply_photo(
                    photo=imdb.get('poster'),
                    caption=cap[:1024],
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except:
                result_msg = await message.reply_text(
                    cap,
                    reply_markup=InlineKeyboardMarkup(btn)
                )
        else:
            result_msg = await message.reply_text(
                cap,
                reply_markup=InlineKeyboardMarkup(btn)
            )
        
        # Auto delete both messages after 5 minutes
        asyncio.create_task(delete_messages_after_delay(result_msg, message, 300))
        
    except Exception as e:
        logger.exception(e)

async def advantage_spell_chok(msg):
    query = re.sub(r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)", "", msg.text, flags=re.IGNORECASE)
    query = query.strip() + " movie"
    
    g_s = await search_gagala(query)
    g_s += await search_gagala(msg.text)
    gs_parsed = []
    
    if not g_s:
        # Not found after spell check
        not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot - @asfilter_bot
"""
        k = await msg.reply(not_found_msg)
        # Delete only bot message after 2 minutes
        asyncio.create_task(delete_messages_after_delay(k, msg, 120, delete_user=False))
        return
    
    regex = re.compile(r".*(imdb|wikipedia).*", re.IGNORECASE)
    gs = list(filter(regex.match, g_s))
    
    gs_parsed = [re.sub(r'\b(\-([a-zA-Z-\s]*)-\|\s*)|(Par..\s)|(\(((\d+)?(\s*[a-zA-Z–\(\)\/]*)*)\))|(\s:\s)|(–\s)|(\.)|(\s)|(",)|(|\s)|(\|)', '', i) for i in gs]
    
    if not gs_parsed:
        reg = re.compile(r"([(\w]([a-zA-Z\s])*(\s\d{4})?)")
        gs_parsed = list(filter(reg.match, g_s))
    
    movielist = []
    gs_parsed = list(dict.fromkeys(gs_parsed))
    
    if len(gs_parsed) > 3:
        gs_parsed = gs_parsed[:3]
    
    if gs_parsed:
        for mov in gs_parsed:
            imdb_s = await get_poster(mov.strip(), bulk=True)
            if imdb_s:
                movielist += [mov.get('title') for mov in imdb_s]
    else:
        movielist = [s.strip() for s in g_s]
    
    movielist += [(re.sub(r'(\-|\(|\)|_)', '', i, flags=re.IGNORECASE)).strip() for i in gs_parsed]
    movielist = list(dict.fromkeys(movielist))
    
    if not movielist:
        # No suggestions found
        not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot - @asfilter_bot
"""
        k = await msg.reply(not_found_msg)
        # Delete only bot message after 2 minutes
        asyncio.create_task(delete_messages_after_delay(k, msg, 120, delete_user=False))
        return
    
    SPELL_CHECK[msg.id] = movielist
    btn = [[InlineKeyboardButton(text=movie.strip(), callback_data=f"spolling#{msg.from_user.id}#{k}")] for k, movie in enumerate(movielist)]
    btn.append([InlineKeyboardButton(text="Close", callback_data=f'spolling#{msg.from_user.id}#close_spellcheck')])
    
    await msg.reply_text(
        "I couldn't find anything related to that\nDid you mean any one of these?",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await query.message.delete()
    
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
                await query.message.edit_text("I'm not connected to any groups!", quote=True)
                return await query.answer('Piracy Is Crime')
        
        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            title = query.message.chat.title
        
        else:
            return await query.answer('Piracy Is Crime')
        
        st = await client.get_chat_member(grp_id, userid)
        if (st.status != enums.ChatMemberStatus.ADMINISTRATOR) and (st.status != enums.ChatMemberStatus.OWNER) and (str(userid) not in ADMINS):
            return await query.answer("You need to be an Admin to do this!", show_alert=True)
        
        await del_all(query.message, grp_id, title)
    
    elif query.data == "delallcancel":
        userid = query.from_user.id
        chat_type = query.message.chat.type
        
        if chat_type == enums.ChatType.PRIVATE:
            await query.message.edit_text("Process Cancelled!", quote=True)
        
        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            st = await client.get_chat_member(query.message.chat.id, userid)
            if (st.status != enums.ChatMemberStatus.ADMINISTRATOR) and (st.status != enums.ChatMemberStatus.OWNER) and (str(userid) not in ADMINS):
                return await query.answer("You don't have enough rights for this!", show_alert=True)
            
            await query.message.delete()
    
    elif "groupcb" in query.data:
        await query.answer()
        group_id = query.data.split(":")[1]
        
        act = query.data.split(":")[2]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id
        
        if act == "":
            stat = "CONNECT"
            cb = "connectcb"
        else:
            stat = "DISCONNECT"
            cb = "disconnect"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{stat}", callback_data=f"{cb}:{group_id}"),
             InlineKeyboardButton("DELETE", callback_data=f"deletecb:{group_id}")],
            [InlineKeyboardButton("BACK", callback_data="backcb")]
        ])
        
        await query.message.edit_text(
            f"Group Name: **{title}**\nGroup ID: `{group_id}`",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    
    elif "connectcb" in query.data:
        await query.answer()
        group_id = query.data.split(":")[1]
        
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id
        
        mkact = await make_active(str(user_id), str(group_id))
        
        if mkact:
            await query.message.edit_text(
                f"Connected to **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text('Some error occurred!!', parse_mode=enums.ParseMode.MARKDOWN)
        
        return
    
    elif "disconnect" in query.data:
        await query.answer()
        group_id = query.data.split(":")[1]
        
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id
        
        mkinact = await make_inactive(str(user_id))
        
        if mkinact:
            await query.message.edit_text(
                f"Disconnected from **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        
        return
    
    elif "deletecb" in query.data:
        await query.answer()
        user_id = query.from_user.id
        group_id = query.data.split(":")[1]
        
        delcon = await delete_connection(str(user_id), str(group_id))
        
        if delcon:
            await query.message.edit_text("Successfully deleted connection")
        else:
            await query.message.edit_text(f"Some error occurred!!", parse_mode=enums.ParseMode.MARKDOWN)
        
        return
    
    elif query.data == "backcb":
        await query.answer()
        
        userid = query.from_user.id
        groupids = await all_connections(str(userid))
        
        if groupids is None:
            await query.message.edit_text("There are no active connections!! Connect to some groups first.")
            return
        
        buttons = []
        for groupid in groupids:
            try:
                ttl = await client.get_chat(int(groupid))
                title = ttl.title
                active = await if_active(str(userid), str(groupid))
                act = " - ACTIVE" if active else ""
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{title}{act}", 
                            callback_data=f"groupcb:{groupid}:{act}"
                        )
                    ]
                )
            except:
                pass
        
        if buttons:
            await query.message.edit_text(
                "Your connected group details:\n\n",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    
    elif query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        
        if not files_:
            return await query.answer('No such file exist.')
        
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        
        settings = await get_settings(query.message.chat.id)
        
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(
                    file_name='' if title is None else title,
                    file_size='' if size is None else size,
                    file_caption='' if f_caption is None else f_caption
                )
            except Exception as e:
                logger.exception(e)
                f_caption = f_caption
        
        if f_caption is None:
            f_caption = f"{files.file_name}"
        
        try:
            if AUTH_CHANNEL and not await is_subscribed(client, query):
                await query.answer(url=f"https://t.me/{temp.U_NAME}?start={file_id}")
                return
            elif settings['botpm']:
                await query.answer(url=f"https://t.me/{temp.U_NAME}?start={file_id}")
                return
            else:
                await client.send_cached_media(
                    chat_id=query.from_user.id,
                    file_id=file_id,
                    caption=f_caption,
                    protect_content=True if ident == 'filep' else False,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton('Support Group', url=GRP_LNK),
                                InlineKeyboardButton('Updates Channel', url=CHNL_LNK)
                            ]
                        ]
                    )
                )
                await query.answer('Check PM, I have sent files in pm', show_alert=True)
        except UserIsBlocked:
            await query.answer('Unblock the bot first!', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={file_id}")
        except Exception as e:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={file_id}")
    
    elif query.data.startswith("send_fall"):
        temp_var, ident, key, offset = query.data.split("#")
        search = BUTTONS.get(key)
        
        if not search:
            return await query.answer("You are using one of my old messages, please send the request again.", show_alert=True)
        
        await query.answer()
        files, n_offset, total = await get_search_results(search, offset=int(offset), filter=True)
        
        settings = await get_settings(query.message.chat.id)
        
        for file in files:
            title = file.file_name
            size = get_size(file.file_size)
            f_caption = file.caption
            
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption = CUSTOM_FILE_CAPTION.format(
                        file_name='' if title is None else title,
                        file_size='' if size is None else size,
                        file_caption='' if f_caption is None else f_caption
                    )
                except Exception as e:
                    logger.exception(e)
                    f_caption = f_caption
            
            if f_caption is None:
                f_caption = f"{title}"
            
            try:
                await client.send_cached_media(
                    chat_id=query.from_user.id,
                    file_id=file.file_id,
                    caption=f_caption,
                    protect_content=True if ident == 'filep' else False,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton('Support Group', url=GRP_LNK),
                                InlineKeyboardButton('Updates Channel', url=CHNL_LNK)
                            ]
                        ]
                    )
                )
            except FloodWait as e:
                await asyncio.sleep(e.x)
                await client.send_cached_media(
                    chat_id=query.from_user.id,
                    file_id=file.file_id,
                    caption=f_caption,
                    protect_content=True if ident == 'filep' else False,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton('Support Group', url=GRP_LNK),
                                InlineKeyboardButton('Updates Channel', url=CHNL_LNK)
                            ]
                        ]
                    )
                )
            except Exception as e:
                logger.exception(e)
        
        temp.send_all[key] = True
    
    elif query.data.startswith("killfilesdq"):
        ident, key = query.data.split("#")
        
        await query.message.edit_text(f"Deleting...")
        
        files = temp.FILES.get(key)
        
        if not files:
            return await query.message.edit_text("File list is empty!")
        
        for file in files:
            title = file.file_name
            size = get_size(file.file_size)
            f_caption = file.caption
            
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption = CUSTOM_FILE_CAPTION.format(
                        file_name='' if title is None else title,
                        file_size='' if size is None else size,
                        file_caption='' if f_caption is None else f_caption
                    )
                except Exception as e:
                    logger.exception(e)
                    f_caption = f_caption
            
            if f_caption is None:
                f_caption = f"{title}"
            
            try:
                await client.send_cached_media(
                    chat_id=query.from_user.id,
                    file_id=file.file_id,
                    caption=f_caption,
                    protect_content=True if ident == 'filep' else False,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton('Support Group', url=GRP_LNK),
                                InlineKeyboardButton('Updates Channel', url=CHNL_LNK)
                            ]
                        ]
                    )
                )
            except FloodWait as e:
                await asyncio.sleep(e.x)
                await client.send_cached_media(
                    chat_id=query.from_user.id,
                    file_id=file.file_id,
                    caption=f_caption,
                    protect_content=True if ident == 'filep' else False,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton('Support Group', url=GRP_LNK),
                                InlineKeyboardButton('Updates Channel', url=CHNL_LNK)
                            ]
                        ]
                    )
                )
            except Exception as e:
                logger.exception(e)
        
        await query.message.delete()
    
    elif query.data == "generate_stream_link":
        await query.answer()
        user_id = query.from_user.id
        group_id = query.message.chat.id
        
        video = query.message.reply_to_message.video
        
        if video:
            file_id = video.file_id
            file_name = video.file_name if video.file_name else "Video"
            file_size = video.file_size
            
            stream_link = f"https://t.me/{temp.U_NAME}?start=stream_{file_id}"
            
            await query.message.edit_text(
                f"📹 **Stream Link Generated**\n\n"
                f"**File:** {file_name}\n"
                f"**Size:** {get_size(file_size)}\n\n"
                f"**Stream Link:** {stream_link}\n\n"
                f"⚠️ **Note:** This link will expire in 24 hours.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("🔗 Copy Link", callback_data=f"copy_link#{stream_link}"),
                            InlineKeyboardButton("🗑 Delete", callback_data="close_data")
                        ]
                    ]
                )
            )
        else:
            await query.answer("Please reply to a video to generate stream link!", show_alert=True)
    
    elif query.data.startswith("copy_link"):
        stream_link = query.data.split("#")[1]
        
        await query.message.edit_text(
            f"📹 **Stream Link**\n\n"
            f"`{stream_link}`\n\n"
            f"Click on the link above to copy it.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("🔗 Open Link", url=stream_link),
                        InlineKeyboardButton("🗑 Delete", callback_data="close_data")
                    ]
                ]
            )
        )
    
    elif query.data == "pages":
        await query.answer()
    
    elif query.data.startswith("prev"):
        ident, req, key, offset = query.data.split("_")
        
        if int(req) != 0 and query.from_user.id != int(req):
            return await query.answer("This is not for you!", show_alert=True)
        
        try:
            offset = int(offset)
        except:
            offset = 0
        
        search = BUTTONS.get(key)
        
        if not search:
            return await query.answer("You are using one of my old messages, please send the request again.", show_alert=True)
        
        files, n_offset, total = await get_search_results(search, offset=offset, filter=True)
        
        try:
            n_offset = int(n_offset)
        except:
            n_offset = 0
        
        if not files:
            return
        
        settings = await get_settings(query.message.chat.id)
        
        if settings['button']:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"[{get_size(file.file_size)}] {file.file_name}", 
                        callback_data=f'file#{file.file_id}'
                    )
                ]
                for file in files
            ]
        else:
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{file.file_name}",
                        callback_data=f'file#{file.file_id}'
                    ),
                    InlineKeyboardButton(
                        text=f"{get_size(file.file_size)}",
                        callback_data=f'file_#{file.file_id}',
                    )
                ]
                for file in files
            ]
        
        btn.insert(0, 
            [
                InlineKeyboardButton("🤖 Check PM", url=f"https://t.me/{BOT_PM_USERNAME}")
            ]
        )
        
        if 0 < offset <= 10:
            off_set = 0
        elif offset == 0:
            off_set = None
        else:
            off_set = offset - 10
        
        if n_offset == 0:
            btn.append(
                [InlineKeyboardButton("⏪ BACK", callback_data=f"prev_{req}_{key}_{off_set}"),
                 InlineKeyboardButton(f"📃 {math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", 
                                     callback_data="pages")]
            )
        elif off_set is None:
            btn.append(
                [InlineKeyboardButton(f"🗓 {math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", 
                                     callback_data="pages"),
                 InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")]
            )
        else:
            btn.append(
                [
                    InlineKeyboardButton("⏪ BACK", callback_data=f"prev_{req}_{key}_{off_set}"),
                    InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                    InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
                ]
            )
        
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except:
            pass
        await query.answer()

# Other necessary functions
async def manual_filters(client, message):
    group_id = message.chat.id
    name = message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    
    keywords = await get_filters(group_id)
    for keyword in keywords:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)
            
            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")
            
            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            joelkb = await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                reply_to_message_id=reply_id
                            )
                            try:
                                if message.from_user.id in ADMINS:
                                    return joelkb
                            except:
                                return
                        else:
                            button = eval(btn)
                            joelkb = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id
                            )
                            try:
                                if message.from_user.id in ADMINS:
                                    return joelkb
                            except:
                                return
                    elif btn == "[]":
                        joelkb = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                        try:
                            if message.from_user.id in ADMINS:
                                return joelkb
                        except:
                            return
                    else:
                        button = eval(btn)
                        joelkb = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        try:
                            if message.from_user.id in ADMINS:
                                return joelkb
                        except:
                            return
                except Exception as e:
                    logger.exception(e)
                    return
            break
    return False

async def del_all(query, grp_id, title):
    await query.message.delete()
    await delete_all_filters(grp_id)
    
    await asyncio.sleep(2)
    m = await query.message.reply_text(
        f"Successfully removed all filters from **{title}**",
        parse_mode=enums.ParseMode.MARKDOWN
    )
    await asyncio.sleep(5)
    await m.delete()

# Start command handler
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [
            [
                InlineKeyboardButton('🤖 Updates', url=CHNL_LNK),
                InlineKeyboardButton('ℹ️ Help', url="https://t.me/AS_Ro_Bot")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        
        await message.reply(
            script.PM_START_TEXT.format(
                message.from_user.mention,
                temp.U_NAME,
                temp.B_NAME
            ),
            reply_markup=reply_markup
        )
        await asyncio.sleep(300)
        try:
            await message.delete()
            await client.delete_messages(message.chat.id, message.id)
        except:
            pass
    else:
        buttons = [[
            InlineKeyboardButton('➕ Add Me To Your Groups ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ], [
            InlineKeyboardButton('🔍 Search', switch_inline_query_current_chat=''),
            InlineKeyboardButton('🤖 Updates', url=CHNL_LNK)
        ], [
            InlineKeyboardButton('ℹ️ Help', callback_data='help'),
            InlineKeyboardButton('😊 About', callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.PM_START_TEXT.format(
                message.from_user.mention,
                temp.U_NAME,
                temp.B_NAME
            ),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        
        if temp.SET_AFTER:
            await asyncio.sleep(300)
            try:
                await message.delete()
            except:
                pass

# Help command handler
@Client.on_message(filters.command('help') & filters.incoming)
async def help(client, message):
    buttons = [[
        InlineKeyboardButton('🏠 Home', callback_data='start'),
        InlineKeyboardButton('😊 About', callback_data='about')
    ], [
        InlineKeyboardButton('Close 🔒', callback_data='close_data')
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await message.reply_photo(
        photo=random.choice(PICS),
        caption=script.HELP_TXT.format(temp.B_NAME),
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )

# About command handler
@Client.on_message(filters.command('about') & filters.incoming)
async def about(client, message):
    buttons = [[
        InlineKeyboardButton('🏠 Home', callback_data='start'),
        InlineKeyboardButton('Close 🔒', callback_data='close_data')
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await message.reply_photo(
        photo=random.choice(PICS),
        caption=script.ABOUT_TXT.format(temp.B_NAME),
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )

# Auto delete handler for bot's messages
@Client.on_message(filters.command(["delete"]) & filters.group)
async def delete_bot_messages(client, message):
    if message.from_user.id in ADMINS:
        try:
            await message.delete()
        except:
            pass

# Log channel handler
@Client.on_message(filters.chat(LOG_CHANNEL) & filters.incoming)
async def log_channel_handler(client, message):
    # Handle log channel messages
    pass

# PM Filter
@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_filter(client, message):
    # PM filter logic here
    pass

# Add your other handlers and functions below...
# Make sure to import all necessary modules and maintain proper indentation

if __name__ == "__main__":
    # Start the bot
    pass
