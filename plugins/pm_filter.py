# Kanged From @TroJanZheX
import asyncio
import re
import ast
import math
import time
import uuid
import random
import logging

from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from database.connections_mdb import active_connection, all_connections, delete_connection, if_active, make_active, make_inactive
from info import ADMINS, AUTH_CHANNEL, AUTH_USERS, CUSTOM_FILE_CAPTION, AUTH_GROUPS, P_TTI_SHOW_OFF, IMDB, SINGLE_BUTTON, SPELL_CHECK_REPLY, IMDB_TEMPLATE, PICS, SHORTLINK_ENABLED, GOOGLE_SCRIPT_URL
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import get_size, is_subscribed, get_poster, search_gagala, temp, get_settings, save_group_settings
from database.users_chats_db import db # यह db Database क्लास का इंस्टेंस है
from database.ia_filterdb import Media, get_file_details, get_search_results
from database.filters_mdb import (
    del_all,
    find_filter,
    get_filters,
)

# **--- यहाँ सही बदलाव किया गया है ---**
# आपकी फाइल का नाम 'users_chats_db.py' है, इसलिए इंपोर्ट 'database.users_chats_db' से होगा।
from database.users_chats_db import check_if_premium, save_shortlink, get_shortlink, delete_shortlink 

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}

SEARCHING_STICKER = "CAACAgUAAxkBAAEEaHpo6o_5KBv3tkax9p9ZUJ3I2D95KAACBAADwSQxMYnlHW4Ls8gQHgQ"
BOT_PM_USERNAME = "As_freefilterBot"
SHORTLINK_EXPIRY_TIME = 600 # 10 minutes (600 seconds)

async def schedule_delete(message, delay_seconds=300):
    """Deletes the message after a specified delay."""
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Error deleting message: {e}")


@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    # Send sticker while searching
    sticker_message = await message.reply_sticker(SEARCHING_STICKER)
    
    k = await manual_filters(client, message, sticker_msg=sticker_message)
    if k == False:
        # Pass the sticker message to auto_filter
        await auto_filter(client, message, sticker_msg=sticker_message)
    else:
        # Delete sticker if manual filter found something
        try:
            await sticker_message.delete()
        except:
            pass # Sticker might be deleted already if it was a manual filter with a file

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
    
    # --- Shortlink/Premium Logic in Next Page ---
    user_id = query.from_user.id
    is_premium = await check_if_premium(user_id)
    use_shortlink = SHORTLINK_ENABLED and not is_premium
    
    btn = []
    if use_shortlink:
        # Shortlink buttons
        for file in files:
            token = str(uuid.uuid4())
            # **--- यहाँ बदलाव किया गया है ---**
            # अब save_shortlink का इस्तेमाल कर रहे हैं
            await save_shortlink(token, file.file_id) 
            redirect_url = f"{GOOGLE_SCRIPT_URL}?token={token}"
            btn.append([InlineKeyboardButton(f"🔗 {file.file_name}", url=redirect_url)])
    else:
        # Direct file buttons (Premium or Shortlink Disabled)
        pre = 'filep' if settings.get('file_secure') else 'file'
        if settings['button']:
            btn.extend([
                [InlineKeyboardButton(text=f"[📁 {get_size(file.file_size)}] {file.file_name}", callback_data=f'{pre}#{file.file_id}')]
                for file in files
            ])
        else:
            btn.extend([
                [
                    InlineKeyboardButton(text=f"{file.file_name}", callback_data=f'{pre}#{file.file_id}'),
                    InlineKeyboardButton(text=f"📁 {get_size(file.file_size)}", callback_data=f'{pre}#{file.file_id}')
                ]
                for file in files
            ])
    # --- End Shortlink/Premium Logic in Next Page ---
    
    if 0 < offset <= 10:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - 10
        
    # Add PM button to the last page
    pm_button = [InlineKeyboardButton("👉 ᴄʜᴇᴄᴋ ʙᴏᴛ ᴘᴍ 👈", url=f"https://t.me/{BOT_PM_USERNAME}")]

    if n_offset == 0:
        btn.append(
            [InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
             InlineKeyboardButton(f"📃 Pages {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}",
                                  callback_data="pages")]
        )
    elif off_set is None:
        btn.append(
            [InlineKeyboardButton(f"🗓 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
             InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")])
    else:
        btn.append(
            [
                InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"🗓 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
                InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
            ],
        )
    
    # Add PM button to the last row
    btn.append(pm_button) 


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
        # Edit message before deleting
        await query.message.edit_text("❌ ᴄʟᴏsᴇᴅ sᴘᴇʟʟ ᴄʜᴇᴄᴋ ❌")
        await asyncio.sleep(2)
        return await query.message.delete()
        
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer("You are clicking on an old button which is expired.", show_alert=True)
        
    movie = movies[(int(movie_))]
    
    # Show message that bot is checking (Corrected as per request)
    checking_msg = await query.message.edit_text(f'🔍 ᴄʜᴇᴄᴋɪɴɢ ꜰᴏʀ: **{movie}** ɪɴ ᴅᴀᴛᴀʙᴀsᴇ... ⏳')
    
    k = await manual_filters(bot, query.message.reply_to_message, text=movie, is_spellcheck=True) # Check manual filter first
    
    # Custom not found message
    not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot - @asfilter_bot
"""
    
    if k == False: # If manual filter didn't find anything
        files, offset, total_results = await get_search_results(movie, offset=0, filter=True)
        if files:
            k = (movie, files, offset, total_results)
            await auto_filter(bot, query, k, is_spellcheck_result=True) # Pass the callback query as the first argument
        else:
            # Send your custom "not found" message here (Fix: Show not found message if no results after spelling check)
            final_msg = await checking_msg.edit_text(not_found_msg)
            # Delete message after 2 minutes (120 seconds)
            await asyncio.sleep(120)
            try:
                await final_msg.delete()
            except Exception:
                pass
    else:
        # If manual filter worked, delete the checking message.
        try:
            await checking_msg.delete()
        except Exception:
            pass


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
            f"Group Name : **{title}**\nGroup ID : `{group_id}`",
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
                f"Connected to **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text('Some error occurred!!', parse_mode=enums.ParseMode.MARKDOWN)
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
                f"Disconnected from **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!!",
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
                "Successfully deleted connection"
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer('Piracy Is Crime')
    elif query.data == "backcb":
        await query.answer()

        userid = query.from_user.id

        groupids = await all_connections(str(userid))
        if groupids is None:
            await query.message.edit_text(
                "There are no active connections!! Connect to some groups first.",
            )
            return await query.answer('Piracy Is Crime')
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
                            text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                        )
                    ]
                )
            except:
                pass
        if buttons:
            await query.message.edit_text(
                "Your connected group details ;\n\n",
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
            
    # START OF THE CORRECTED CODE BLOCK
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
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files.file_name}"

        # Check if the user is subscribed to the AUTH_CHANNEL
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            # If not subscribed, show a pop-up with a link to the bot
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start=subscribe")
            return
            
        try:
            # Try to send the file to the user's PM
            pm_message = await client.send_cached_media(
                chat_id=query.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=True if ident == "filep" else False 
            )
            
            # Send the warning message in PM
            pm_warning_message = """
Hello,

⚠️ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ 5 ᴍɪɴᴜᴛᴇs

ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇ sᴏᴍᴇᴡʜᴇʀᴇ ʙᴇғᴏʀᴇ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ..

मूवी यहां डाउनलोड ना करे क्योंकि | मूवी 🍿 5 Minutes में डिलीट कर दी जायेगी
कृपया कही फॉरवर्ड करे के डाउनलोड करे
"""
            warning_msg = await client.send_message(
                chat_id=query.from_user.id,
                text=pm_warning_message,
                reply_to_message_id=pm_message.id
            )
            
            # Schedule deletion of the file and warning in PM
            asyncio.create_task(schedule_delete(pm_message, 300))
            asyncio.create_task(schedule_delete(warning_msg, 300))
            
            # If file sending is successful, show the success pop-up in the group
            group_notification = "✅ फ़ाइल आपके PM (प्राइवेट मैसेज) में भेज दी गई है।\n\n✅ File has been sent to your PM."
            await query.answer(group_notification, show_alert=True)
            
        except UserIsBlocked:
            # If the user has blocked the bot
            await query.answer('आपने बॉट को ब्लॉक किया हुआ है। कृपया अनब्लॉक करें।', show_alert=True)
        except PeerIdInvalid:
            # If the user has not started the bot yet
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
        except Exception as e:
            # For any other errors
            logger.exception(e)
            await query.answer(f"An error occurred: {e}", show_alert=True)
            
    # END OF THE CORRECTED CODE BLOCK

    elif query.data.startswith("checksub"):
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer("I Like Your Smartness, But Don't Be Oversmart 😒", show_alert=True)
            return
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('No such file exist.')
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
        
        # Send PM file
        pm_message = await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == 'checksubp' else False
        )
        
        # Send separate PM message
        pm_warning_message = """
Hello,

⚠️ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ 5 ᴍɪɴᴜᴛᴇs

ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇ sᴏᴍᴇᴡʜᴇʀᴇ ʙᴇғᴏʀᴇ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ..

मूवी यहां डाउनलोड ना करे क्योंकि | मूवी 🍿 5 Minutes में डिलीट कर दी जायेगी
कृपया कही फॉरवर्ड करे के डाउनलोड करे
"""
        warning_msg = await client.send_message(
            chat_id=query.from_user.id,
            text=pm_warning_message,
            reply_to_message_id=pm_message.id
        )
        
        # Delete PM file and warning message after 5 minutes
        asyncio.create_task(schedule_delete(pm_message, 300))
        asyncio.create_task(schedule_delete(warning_msg, 300))
        
    elif query.data == "pages":
        await query.answer()
    elif query.data == "start":
        buttons = [[
            InlineKeyboardButton('➕ Add Me To Your Groups ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ], [
            InlineKeyboardButton('🔍 Search', switch_inline_query_current_chat=''),
            InlineKeyboardButton('🤖 Updates', url='https://t.me/asbhai_bsr')
        ], [
            InlineKeyboardButton('ℹ️ Help', callback_data='help'),
            InlineKeyboardButton('😊 About', callback_data='about')
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
            InlineKeyboardButton('Manual Filter', callback_data='manuelfilter'),
            InlineKeyboardButton('Auto Filter', callback_data='autofilter')
        ], [
            InlineKeyboardButton('Connection', callback_data='coct'),
            InlineKeyboardButton('Extra Mods', callback_data='extra')
        ], [
            InlineKeyboardButton('🏠 Home', callback_data='start'),
            InlineKeyboardButton('🔮 Status', callback_data='stats')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.HELP_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "about":
        buttons = [[
            InlineKeyboardButton('🤖 Updates', url='https://t.me/asbhai_bsr'),
            InlineKeyboardButton('♥️ Source', callback_data='source')
        ], [
            InlineKeyboardButton('🏠 Home', callback_data='start'),
            InlineKeyboardButton('🔐 Close', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "source":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 Back', callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.SOURCE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "manuelfilter":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 Back', callback_data='help'),
            InlineKeyboardButton('⏹️ Buttons', callback_data='button')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.MANUELFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "button":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 Back', callback_data='manuelfilter')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.BUTTON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "autofilter":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 Back', callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.AUTOFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "coct":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 Back', callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CONNECTION_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "extra":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 Back', callback_data='help'),
            InlineKeyboardButton('👮‍♂️ Admin', callback_data='admin')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.EXTRAMOD_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "admin":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 Back', callback_data='extra')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ADMIN_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "stats":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 Back', callback_data='help'),
            InlineKeyboardButton('♻️', callback_data='rfrsh')
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
        await query.answer("Fetching MongoDb DataBase")
        buttons = [[
            InlineKeyboardButton('👩‍🦯 Back', callback_data='help'),
            InlineKeyboardButton('♻️', callback_data='rfrsh')
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
            await query.message.edit("Your Active Connection Has Been Changed. Go To /settings.")
            return await query.answer('Piracy Is Crime')

        if status == "True":
            await save_group_settings(grpid, set_type, False)
        else:
            await save_group_settings(grpid, set_type, True)

        settings = await get_settings(grpid)

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Filter Button',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Single' if settings["button"] else 'Double',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Bot PM', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["botpm"] else '❌ No',
                                         callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('File Secure',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["file_secure"] else '❌ No',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('IMDB', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["imdb"] else '❌ No',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Spell Check',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["spell_check"] else '❌ No',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Welcome', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["welcome"] else '❌ No',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_reply_markup(reply_markup)
    await query.answer('Piracy Is Crime')

# --- MODIFIED: Start command with 10-minute token expiry logic ---

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [
            [InlineKeyboardButton('🤖 Updates', url='https://t.me/asbhai_bsr')],
            [InlineKeyboardButton('ℹ️ Help', url=f"https://t.me/{temp.U_NAME}?start=help")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(script.START_TXT.format(message.from_user.mention if message.from_user else message.chat.title, temp.U_NAME, temp.B_NAME), reply_markup=reply_markup)
        return

    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        # Note: LOG_CHANNEL is assumed to be defined elsewhere (e.g., in info.py)
        # Assuming LOG_CHANNEL is defined or you can remove this log part if not needed
        # await client.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))

    # --- शॉर्टलिंक से रीडायरेक्ट होने वाले यूजर्स के लिए लॉजिक ---
    if len(message.command) > 1 and message.command[1].startswith("download_"):
        token = message.command[1].split("_")[1]
        # **--- यहाँ बदलाव किया गया है ---**
        # अब get_shortlink का इस्तेमाल कर रहे हैं
        file_info = await get_shortlink(token) 

        if file_info:
            file_id = file_info.get("file_id")
            token_timestamp = file_info.get("timestamp")

            try:
                time_difference = time.time() - token_timestamp.timestamp()
            except AttributeError:
                # Handle case where token_timestamp is not a datetime object (though it should be)
                time_difference = 0 
            
            if time_difference > SHORTLINK_EXPIRY_TIME:
                # **--- यहाँ बदलाव किया गया है ---**
                # अब delete_shortlink का इस्तेमाल कर रहे हैं
                await delete_shortlink(token) 
                return await message.reply("यह डाउनलोड लिंक **समय सीमा से बाहर** (Expired) हो गया है। कृपया बॉट में फिर से फ़ाइल खोजें।")

            files_ = await get_file_details(file_id)
            if not files_:
                return await message.reply('फ़ाइल मौजूद नहीं है।')

            file = files_[0]
            f_caption = file.caption or f"{file.file_name}"
            
            try:
                sent_msg = await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=file_id,
                    caption=f_caption
                )
                
                # Send PM warning message
                pm_warning_message = """
Hello,

⚠️ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ 5 ᴍɪɴᴜᴛᴇs

ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇ sᴏᴍᴇᴡʜᴇʀᴇ ʙᴇғᴏʀᴇ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ..

मूवी यहां डाउनलोड ना करे क्योंकि | मूवी 🍿 5 Minutes में डिलीट कर दी जायेगी
कृपया कही फॉरवर्ड करे के डाउनलोड करे
"""
                warning_msg = await client.send_message(
                    chat_id=message.from_user.id,
                    text=pm_warning_message,
                    reply_to_message_id=sent_msg.id
                )
                
                # Schedule deletion of the file and warning in PM
                asyncio.create_task(schedule_delete(sent_msg, 300))
                asyncio.create_task(schedule_delete(warning_msg, 300))
                
                # Finally delete the token after successful sending
                await delete_shortlink(token)

            except Exception as e:
                logger.error(e)
                await message.reply("फ़ाइल भेजने में कोई त्रुटि हुई।")
        else:
            await message.reply("यह डाउनलोड लिंक **अमान्य** या **समाप्त** हो गया है।")
        return
        
    # --- सामान्य /start कमांड लॉजिक --- (बाकी कोड जैसा का तैसा)
    
    if len(message.command) != 2:
        buttons = [[
            InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ],[
            InlineKeyboardButton('✨ Buy Premium ✨', callback_data='buy_premium'),
            InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')
        ],[
            InlineKeyboardButton('ℹ️ ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇs', url='https://t.me/asbhai_bsr')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        # Note: PICS is assumed to be defined elsewhere (e.g., in info.py)
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return
        
    # --- Deep Link and File ID Lookup Logic ---
    if message.command[1].lower() == "help":
        buttons = [[
            InlineKeyboardButton('Manual Filter', callback_data='manuelfilter'),
            InlineKeyboardButton('Auto Filter', callback_data='autofilter')
        ], [
            InlineKeyboardButton('Connection', callback_data='coct'),
            InlineKeyboardButton('Extra Mods', callback_data='extra')
        ], [
            InlineKeyboardButton('🏠 Home', callback_data='start'),
            InlineKeyboardButton('🔮 Status', callback_data='stats')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(
            text=script.HELP_TXT.format(message.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return
        
    # Check for file deep link format
    # The file deep link format is assumed to be 'file_[file_id]' or 'filep_[file_id]'
    # We must handle both 'file' and 'filep' as part of the check
    if "_" not in message.command[1]:
        # Handle start parameters that are not file IDs or help/subscribe
        return

    # Assuming the format is 'ident_file_id' (e.g., 'file_ABC', 'filep_XYZ', 'subscribe')
    ident, file_id = message.command[1].split("_", 1)
    
    if message.command[1] == "subscribe":
        # Subscription button for AUTH_CHANNEL
        buttons = [[
            InlineKeyboardButton('🤖 Updates', url='https://t.me/asbhai_bsr')
        ]]
        if AUTH_CHANNEL:
            try:
                # Note: AUTH_CHANNEL is assumed to be defined elsewhere (e.g., in info.py)
                invite_link = await client.create_chat_invite_link(AUTH_CHANNEL)
                buttons.append([InlineKeyboardButton("Join Channel", url=invite_link.invite_link)])
            except Exception as e:
                logger.error(f"Error creating invite link: {e}")
        
        buttons.append([InlineKeyboardButton('🏠 Home', callback_data='start')])
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text("You must join the channel to use this bot's functions.", reply_markup=reply_markup)
        return

    files_ = await get_file_details(file_id)
    if not files_:
        await message.reply('No such file exist.')
        return
        
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
        f_caption = f"{files.file_name}"
        
    if AUTH_CHANNEL and not await is_subscribed(client, message):
        # If user is not subscribed, send the subscribe button
        buttons = [[
            InlineKeyboardButton('🤖 Updates', url='https://t.me/asbhai_bsr')
        ]]
        try:
            invite_link = await client.create_chat_invite_link(AUTH_CHANNEL)
            buttons.append([InlineKeyboardButton("Join Channel", url=invite_link.invite_link)])
        except Exception as e:
            logger.error(f"Error creating invite link: {e}")

        buttons.append([InlineKeyboardButton('🏠 Home', callback_data='start')])
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text("You must join the channel to get this file.", reply_markup=reply_markup)
        return
        
    # --- File Sending Logic (for deep link) ---
    try:
        sent_msg = await client.send_cached_media(
            chat_id=message.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == "filep" else False
        )
        
        # Send PM warning message
        pm_warning_message = """
Hello,

⚠️ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ 5 ᴍɪɴᴜᴛᴇs

ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇ sᴏᴍᴇᴡʜᴇʀᴇ ʙᴇғᴏʀᴇ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ..

मूवी यहां डाउनलोड ना करे क्योंकि | मूवी 🍿 5 Minutes में डिलीट कर दी जायेगी
कृपया कही फॉरवर्ड करे के डाउनलोड करे
"""
        warning_msg = await client.send_message(
            chat_id=message.from_user.id,
            text=pm_warning_message,
            reply_to_message_id=sent_msg.id
        )
        
        # Schedule deletion of the file and warning in PM
        asyncio.create_task(schedule_delete(sent_msg, 300))
        asyncio.create_task(schedule_delete(warning_msg, 300))
        
    except Exception as e:
        logger.error(e)
        await message.reply("फ़ाइल भेजने में कोई त्रुटि हुई।")
        
async def auto_filter(client, msg, spoll=False, sticker_msg: Message = None, is_spellcheck_result=False):
    # Use the original message object correctly
    message = msg.message.reply_to_message if is_spellcheck_result else msg
    
    if not spoll:
        settings = await get_settings(message.chat.id)
        if message.text.startswith("/") or re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            if sticker_msg: await sticker_msg.delete()
            return
        if not (2 < len(message.text) < 100):
            if sticker_msg: 
                try: await sticker_msg.delete()
                except: pass
            return
        
        search = message.text
        files, offset, total_results = await get_search_results(search.lower(), offset=0, filter=True)
        if sticker_msg: 
            try: await sticker_msg.delete()
            except: pass
        
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
                k = await msg.reply(not_found_msg)
                await asyncio.sleep(120)
                try: await k.delete()
                except: pass
                return
    else:
        settings = await get_settings(message.chat.id)
        search, files, offset, total_results = spoll

    # --- प्रीमियम और शॉर्टलिंक लॉजिक यहाँ से शुरू होता है ---
    user_id = message.from_user.id if message.from_user else 0 # Ensure user_id is set
    is_premium = await check_if_premium(user_id)
    use_shortlink = SHORTLINK_ENABLED and not is_premium

    btn = []
    if use_shortlink:
        # शॉर्टलिंक का उपयोग करें
        for file in files:
            token = str(uuid.uuid4())
            # **--- यहाँ बदलाव किया गया है ---**
            # अब save_shortlink का इस्तेमाल कर रहे हैं
            await save_shortlink(token, file.file_id) 
            redirect_url = f"{GOOGLE_SCRIPT_URL}?token={token}"
            btn.append([InlineKeyboardButton(f"🔗 {file.file_name}", url=redirect_url)])
    else:
        # डायरेक्ट फाइल भेजें (प्रीमियम यूजर्स या जब शॉर्टलिंक बंद हो)
        pre = 'filep' if settings.get('file_secure') else 'file'
        if settings.get("button"):
            btn.extend([[InlineKeyboardButton(f"[📁 {get_size(file.file_size)}] {file.file_name}", callback_data=f'{pre}#{file.file_id}')] for file in files])
        else:
            btn.extend([[InlineKeyboardButton(text=f"{file.file_name}", callback_data=f'{pre}#{file.file_id}'), InlineKeyboardButton(text=f"📁 {get_size(file.file_size)}", callback_data=f'{pre}#{file.file_id}')] for file in files])

    if offset != "":
        key = f"{message.chat.id}-{message.id}"
        BUTTONS[key] = search
        req = message.from_user.id or 0
        btn.append([InlineKeyboardButton(text=f"🗓 1/{math.ceil(total_results/10)}", callback_data="pages"), InlineKeyboardButton(text="NEXT ⏩", callback_data=f"next_{req}_{key}_{offset}")])
    else:
        btn.append([InlineKeyboardButton(text="🗓 1/1", callback_data="pages")])
    
    imdb = await get_poster(search, file=files[0].file_name) if settings.get("imdb") else None
    
    try:
        req_by = message.from_user.mention
    except:
        req_by = "User"
        
    custom_caption = f"""
📂 ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ - **{search}**

📢 ʀᴇǫᴜᴇꜱᴛᴇᴅ ʙʏ - {req_by}
"""
    if use_shortlink:
        custom_caption += "\n\n*वेरिफिकेशन पूरा करके फ़ाइल डाउनलोड करें।*"
    else:
        custom_caption += "\n\n🍿 Your Movie Files 👇"

    if imdb and imdb.get('poster'):
        await message.reply_photo(photo=imdb['poster'], caption=custom_caption, reply_markup=InlineKeyboardMarkup(btn))
    else:
        await message.reply_text(custom_caption, reply_markup=InlineKeyboardMarkup(btn))

    if is_spellcheck_result:
        try: await msg.message.delete()
        except: pass
    
    if not settings["spell_check"]:
        return 
        
    processing_msg = await msg.reply_text('🧐 **Checking spelling...** Please wait ⏳')
    
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", message.text, flags=re.IGNORECASE)
    query = query.strip() + " movie"
    g_s = await search_gagala(query)
    g_s += await search_gagala(message.text)
    gs_parsed = []
    
    not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot - @asfilter_bot
"""
    
    if not g_s:
        final_msg = await processing_msg.edit_text(not_found_msg)
        await asyncio.sleep(120)
        try:
            await final_msg.delete()
        except Exception:
            pass
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
    user = message.from_user.id if message.from_user else 0
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
        final_msg = await processing_msg.edit_text(not_found_msg)
        await asyncio.sleep(120)
        try:
            await final_msg.delete()
        except Exception:
            pass
        return
        
    SPELL_CHECK[message.id] = movielist
    btn = [[
        InlineKeyboardButton(
            text=movie.strip(),
            callback_data=f"spolling#{user}#{k}",
        )
    ] for k, movie in enumerate(movielist)]
    btn.append([InlineKeyboardButton(text="❌ ᴄʟᴏsᴇ sᴘᴇʟʟ ᴄʜᴇᴄᴋ ❌", callback_data=f'spolling#{user}#close_spellcheck')])
    
    await processing_msg.edit_text("🤔 ɪ ᴄᴏᴜʟᴅɴ'ᴛ ꜰɪɴᴅ ᴀɴʏᴛʜɪɴɢ ʀᴇʟᴀᴛᴇᴅ ᴛᴏ ᴛʜᴀᴛ\n\n**ᴅɪᴅ ʏᴏᴜ ᴍᴇᴀɴ ᴀɴʏ ᴏɴᴇ ᴏꜰ ᴛʜᴇsᴇ?**",
                                    reply_markup=InlineKeyboardMarkup(btn))


async def advantage_spell_chok(message):
    processing_msg = await message.reply_text('🧐 **Checking spelling...** Please wait ⏳')
    
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", message.text, flags=re.IGNORECASE)
    query = query.strip() + " movie"
    g_s = await search_gagala(query)
    g_s += await search_gagala(message.text)
    gs_parsed = []
    
    not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot - @asfilter_bot
"""
    
    if not g_s:
        final_msg = await processing_msg.edit_text(not_found_msg)
        await asyncio.sleep(120)
        try:
            await final_msg.delete()
        except Exception:
            pass
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
    user = message.from_user.id if message.from_user else 0
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
        final_msg = await processing_msg.edit_text(not_found_msg)
        await asyncio.sleep(120)
        try:
            await final_msg.delete()
        except Exception:
            pass
        return
        
    SPELL_CHECK[message.id] = movielist
    btn = [[
        InlineKeyboardButton(
            text=movie.strip(),
            callback_data=f"spolling#{user}#{k}",
        )
    ] for k, movie in enumerate(movielist)]
    btn.append([InlineKeyboardButton(text="❌ ᴄʟᴏsᴇ sᴘᴇʟʟ ᴄʜᴇᴄᴋ ❌", callback_data=f'spolling#{user}#close_spellcheck')])
    
    await processing_msg.edit_text("🤔 ɪ ᴄᴏᴜʟᴅɴ'ᴛ ꜰɪɴᴅ ᴀɴʏᴛʜɪɴɢ ʀᴇʟᴀᴛᴇᴅ ᴛᴏ ᴛʜᴀᴛ\n\n**ᴅɪᴅ ʏᴏᴜ ᴍᴇᴀɴ ᴀɴʏ ᴏɴᴇ ᴏꜰ ᴛʜᴇsᴇ?**",
                                    reply_markup=InlineKeyboardMarkup(btn))


async def manual_filters(client, message, text=False, sticker_msg: Message = None, is_spellcheck=False):
    group_id = message.chat.id
    name = text or message.text
    # Get the ID of the original message to reply to, or the new message ID if no reply is available.
    reply_id = message.reply_to_message.id if message.reply_to_message and not is_spellcheck else message.id
    keywords = await get_filters(group_id)
    
    if is_spellcheck: # For spell check manual filter, reply to the original user's message
        reply_id = message.id
        
    # Delete sticker before sending the manual filter response
    if sticker_msg: 
        try:
            await sticker_msg.delete()
        except:
            pass

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
                            result_msg = await client.send_message(group_id, reply_text, disable_web_page_preview=True)
                        else:
                            button = eval(btn)
                            result_msg = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id
                            )
                    elif btn == "[]":
                        result_msg = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                    else:
                        button = eval(btn)
                        result_msg = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        
                    # Delete the result message after 5 minutes (300 seconds)
                    asyncio.create_task(schedule_delete(result_msg, 300))
                    
                except Exception as e:
                    logger.exception(e)
                return True # Return True if manual filter was found and sent
    else:
        return False # Return False if no manual filter was found
