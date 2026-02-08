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
    SINGLE_BUTTON, SPELL_CHECK_REPLY, IMDB_TEMPLATE, LINK_MODE
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
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

# New sticker ID and bot username (as per your request)
SEARCHING_STICKER = "CAACAgUAAxkBAAEEaHpo6o_5KBv3tkax9p9ZUJ3I2D95KAACBAADwSQxMYnlHW4Ls8gQHgQ"
BOT_PM_USERNAME = "As_freefilterBot"


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
    
    # LINK_MODE Logic (same as auto_filter)
    pre = 'filep' if settings['file_secure'] else 'file'
    if LINK_MODE:
        # LINK_MODE True hai to Direct Link wala button banega
        btn = [
            [
                InlineKeyboardButton(
                    text=f"📂 {get_size(file.file_size)} | {file.file_name}",
                    url=f"https://t.me/{temp.U_NAME}?start=file_{file.file_id}"
                ),
            ]
            for file in files
        ]
    elif settings["button"]:
        # Agar Button Mode (Single Button) hai
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[📁 {get_size(file.file_size)}] {file.file_name}", callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        # Agar Double Button hai
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{file.file_name}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
                InlineKeyboardButton(
                    text=f"📁 {get_size(file.file_size)}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
            ]
            for file in files
        ]

    if 0 < offset <= 10:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - 10
        
    # Add PM button to the last page with new text
    pm_button = [InlineKeyboardButton("(⋆. 𐙚˚࿔ 𝗖𝗹𝗶𝗰𝗸 𝗵𝗲𝗿𝗲 𝘁𝗼 𝗴𝗲𝘁 𝘁𝗵𝗲 𝗳𝗶𝗹𝗲 ᯓᡣ𐭩˚⋆)", url=f"https://t.me/{BOT_PM_USERNAME}")]

    # IMPROVEMENT: If only one page exists, show "No More Pages" instead of page numbers
    total_pages = math.ceil(total / 10)
    current_page = math.ceil(int(offset) / 10) + 1
    
    if n_offset == 0:
        # This means no next page exists
        if off_set is None:
            # Only one page exists
            btn.append(
                [InlineKeyboardButton("🚫 𝗡𝗼 𝗠𝗼𝗿𝗲 𝗣𝗮𝗴𝗲𝘀 🚫", callback_data="pages")]
            )
        else:
            btn.append(
                [InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
                 InlineKeyboardButton(f"📃 Pages {current_page} / {total_pages}",
                                      callback_data="pages")]
            )
    elif off_set is None:
        btn.append(
            [InlineKeyboardButton(f"📃 Pages {current_page} / {total_pages}", callback_data="pages"),
             InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")])
    else:
        btn.append(
            [
                InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"📃 Pages {current_page} / {total_pages}", callback_data="pages"),
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
        try:
            await query.message.delete()
            # User ka message delete NAHI karo - NOT FOUND CASE
        except Exception:
            pass
        return
        
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer("You are clicking on an old button which is expired.", show_alert=True)
        
    movie = movies[(int(movie_))]
    
    # Show message that bot is checking
    checking_msg = await query.message.edit_text(f'🔍 ᴄʜᴇᴄᴋɪɴɢ ꜰᴏʀ: **{movie}** ɪɴ ᴅᴀᴛᴀʙᴀsᴇ... ⏳')
    
    k = await manual_filters(bot, query.message.reply_to_message, text=movie, is_spellcheck=True)
    
    # Custom not found message with button
    not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot
"""
    
    if k == False:
        files, offset, total_results = await get_search_results(movie, offset=0, filter=True)
        if files:
            k = (movie, files, offset, total_results)
            await auto_filter(bot, query, k, is_spellcheck_result=True)
        else:
            # Create inline button for other bot
            other_bot_button = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔍 Search Other Bot", url="t.me/asfilter_bot")
            ]])
            
            final_msg = await checking_msg.edit_text(
                not_found_msg, 
                reply_markup=other_bot_button
            )
            # Delete only bot's message after 2 minutes (120 seconds)
            # USER KA MESSAGE DELETE NAHI HOGA - NOT FOUND CASE
            await asyncio.sleep(120)
            try:
                await final_msg.delete()
                # User ka message delete NAHI karo - NOT FOUND CASE
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
            
    # CORRECTED FILE SENDING SECTION WITH GROUP NOTIFICATION
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
            # FIRST: Show popup message in group that file is being sent to PM
            group_notification = "✅ फ़ाइल आपके PM में भेजी जा रही है...\n\n✅ File is being sent to your PM..."
            await query.answer(group_notification, show_alert=True)
            
            # SECOND: Try to send the file to the user's PM
            pm_message = await client.send_cached_media(
                chat_id=query.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=True if ident == "filep" else False 
            )
            
            # THIRD: Send the warning message in PM with updated text
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
            
            # FOURTH: Send success message in group that will auto-delete after 3 seconds
            success_msg = await query.message.reply_text(
                f"✅ फ़ाइल {query.from_user.mention} के PM में भेज दी गई है!\n\n✅ File has been sent to {query.from_user.mention}'s PM!"
            )
            
            # Schedule deletion of messages
            await asyncio.sleep(3)  # Delete group success message after 3 seconds
            try:
                await success_msg.delete()
            except Exception:
                pass
                
            await asyncio.sleep(297)  # Wait remaining time for PM messages (total 5 minutes)
            try:
                await pm_message.delete()
                await warning_msg.delete()
            except Exception:
                pass
            
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
        
        # Show popup that file is being sent
        await query.answer("✅ फ़ाइल आपके PM में भेजी जा रही है...", show_alert=True)
        
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
        
        # Send group success message
        success_msg = await query.message.reply_text(
            f"✅ फ़ाइल {query.from_user.mention} के PM में भेज दी गई है!"
        )
        
        # Delete group message after 3 seconds
        await asyncio.sleep(3)
        try:
            await success_msg.delete()
        except Exception:
            pass
        
        # Delete PM file and warning message after 5 minutes
        await asyncio.sleep(297)
        try:
            await pm_message.delete()
            await warning_msg.delete()
        except Exception:
            pass
        
    elif query.data == "pages":
        await query.answer()
        
    elif query.data == "start":
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


async def auto_filter(client, msg, spoll=False, sticker_msg: Message = None, is_spellcheck_result=False):
    # Determine the message object to use
    if is_spellcheck_result:
        # For spellcheck result, use the original message that was replied to
        message = msg.message.reply_to_message if msg.message.reply_to_message else msg.message
    else:
        message = msg
    
    if not spoll:
        settings = await get_settings(message.chat.id)
        if message.text.startswith("/"): 
            if sticker_msg: 
                try:
                    await sticker_msg.delete()
                except:
                    pass
            return  # ignore commands
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            if sticker_msg: 
                try:
                    await sticker_msg.delete()
                except:
                    pass
            return
        if 2 < len(message.text) < 100:
            search = message.text
            
            # First try exact search
            files, offset, total_results = await get_search_results(search.lower(), offset=0, filter=True)
            
            # Delete sticker immediately after getting search results
            if sticker_msg: 
                try:
                    await sticker_msg.delete() 
                except:
                    pass
            
            # Custom not found message with button
            not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot
"""
            
            # Create inline button for other bot
            other_bot_button = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔍 Search Other Bot", url="t.me/asfilter_bot")
            ]])

            if not files:
                # Try spelling correction
                corrected_search = await correct_spelling(search)
                
                if corrected_search and corrected_search.lower() != search.lower():
                    # Try with corrected spelling
                    files, offset, total_results = await get_search_results(corrected_search.lower(), offset=0, filter=True)
                    
                    if files:
                        # Show that we're using corrected spelling
                        search = corrected_search
                    else:
                        if settings["spell_check"]:
                            # Pass the original message for spell check
                            return await advantage_spell_chok(msg)
                        else:
                            # Send custom not found message with button
                            k = await message.reply(
                                not_found_msg, 
                                reply_markup=other_bot_button
                            )
                            # Delete only bot's message after 2 minutes (120 seconds)
                            # USER KA SEARCH MESSAGE DELETE NAHI HOGA - NOT FOUND CASE
                            await asyncio.sleep(120)
                            try:
                                await k.delete()
                                # USER KA MESSAGE DELETE NAHI KARO - NOT FOUND CASE
                            except Exception:
                                pass
                            return
                else:
                    if settings["spell_check"]:
                        # Pass the original message for spell check
                        return await advantage_spell_chok(msg)
                    else:
                        # Send custom not found message with button
                        k = await message.reply(
                            not_found_msg, 
                            reply_markup=other_bot_button
                        )
                        # Delete only bot's message after 2 minutes (120 seconds)
                        # USER KA SEARCH MESSAGE DELETE NAHI HOGA - NOT FOUND CASE
                        await asyncio.sleep(120)
                        try:
                            await k.delete()
                            # USER KA MESSAGE DELETE NAHI KARO - NOT FOUND CASE
                        except Exception:
                            pass
                        return
        else:
            if sticker_msg: 
                try:
                    await sticker_msg.delete()
                except:
                    pass
            return
    else:
        # If it's a result from spell check
        settings = await get_settings(message.chat.id)
        search, files, offset, total_results = spoll
        
    pre = 'filep' if settings['file_secure'] else 'file'
    
    # ---------- LINK_MODE LOGIC ADDED HERE ----------
    if LINK_MODE:
        # Agar LINK_MODE True hai to Direct Link wala button banega
        btn = [
            [
                InlineKeyboardButton(
                    text=f"📂 {get_size(file.file_size)} | {file.file_name}",
                    url=f"https://t.me/{temp.U_NAME}?start=file_{file.file_id}"
                ),
            ]
            for file in files
        ]
    elif settings["button"]:
        # Agar Button Mode (Single Button) hai
        btn = [
            [
                InlineKeyboardButton(
                    text=f"[📁 {get_size(file.file_size)}] {file.file_name}", callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        # Agar Double Button hai
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{file.file_name}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
                InlineKeyboardButton(
                    text=f"📁 {get_size(file.file_size)}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
            ]
            for file in files
        ]
    # ------------------------------------------------

    # Add PM button with updated text
    pm_button = [InlineKeyboardButton("(⋆. 𐙚˚࿔ 𝗖𝗹𝗶𝗰𝗸 𝗵𝗲𝗿𝗲 𝘁𝗼 𝗴𝗲𝘁 𝘁𝗵𝗲 𝗳𝗶𝗹𝗲 ᯓᡣ𐭩˚⋆)", url=f"https://t.me/{BOT_PM_USERNAME}")]

    # IMPROVEMENT: If only one page exists, show "No More Pages" instead of page numbers
    total_pages = math.ceil(int(total_results) / 10) if total_results else 1
    current_page = math.ceil(int(offset) / 10) + 1
    
    if offset != "":
        key = f"{message.chat.id}-{message.id}"
        BUTTONS[key] = search
        req = message.from_user.id if message.from_user else 0
        
        # Check if this is the only page
        if total_pages == 1:
            btn.append(
                [InlineKeyboardButton("🚫 𝗡𝗼 𝗠𝗼𝗿𝗲 𝗣𝗮𝗴𝗲𝘀 🚫", callback_data="pages")]
            )
        else:
            btn.append(
                [InlineKeyboardButton(text=f"📃 Pages {current_page}/{total_pages}", callback_data="pages"),
                 InlineKeyboardButton(text="NEXT ⏩", callback_data=f"next_{req}_{key}_{offset}")]
            )
    else:
        # Only one page exists
        btn.append(
            [InlineKeyboardButton("🚫 𝗡𝗼 𝗠𝗼𝗿𝗲 𝗣𝗮𝗴𝗲𝘀 🚫", callback_data="pages")]
        )
    
    # Add PM button to the last row
    btn.append(pm_button) 

    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    
    # Custom Caption setup
    try:
        req_by = message.from_user.mention
    except:
        req_by = "User"
    try:
        group_title = message.chat.title
    except:
        group_title = "Group"
        
    # The new result message template
    custom_caption = f"""
📂 ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ - **{search}**

📢 ʀᴇǫᴜᴇꜱᴛᴇᴅ ʙʏ - {req_by}
♾️ ᴘᴏᴡᴇᴇᴅ ʙʏ - {group_title}

🍿 Your Movie Files 👇
"""
    
    TEMPLATE = settings.get('template', IMDB_TEMPLATE)
    
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
        # Prepend custom header to IMDB caption
        cap = custom_caption + "\n" + cap
        
    else:
        # Use custom header for non-IMDB caption
        cap = custom_caption
        
    if imdb and imdb.get('poster'):
        try:
            # Send photo and then delete the result message after 5 minutes
            result_msg = await message.reply_photo(photo=imdb.get('poster'), caption=cap[:1024],
                                      reply_markup=InlineKeyboardMarkup(btn))
            
            await asyncio.sleep(300)  # 5 minutes
            try:
                await result_msg.delete()  # Bot ka result delete
                # USER KA SEARCH MESSAGE DELETE HONA CHAHIYE - MOVIE MIL GAYI ✅
                await message.delete()     # USER KA SEARCH MESSAGE DELETE ✅
            except Exception:
                pass
            
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            # Send photo and then delete the result message after 5 minutes
            result_msg = await message.reply_photo(photo=poster, caption=cap[:1024], reply_markup=InlineKeyboardMarkup(btn))
            
            await asyncio.sleep(300)  # 5 minutes
            try:
                await result_msg.delete()  # Bot ka result delete
                # USER KA SEARCH MESSAGE DELETE HONA CHAHIYE - MOVIE MIL GAYI ✅
                await message.delete()     # USER KA SEARCH MESSAGE DELETE ✅
            except Exception:
                pass
            
        except Exception as e:
            logger.exception(e)
            # Send text and then delete the result message after 5 minutes
            result_msg = await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))
            
            await asyncio.sleep(300)  # 5 minutes
            try:
                await result_msg.delete()  # Bot ka result delete
                # USER KA SEARCH MESSAGE DELETE HONA CHAHIYE - MOVIE MIL GAYI ✅
                await message.delete()     # USER KA SEARCH MESSAGE DELETE ✅
            except Exception:
                pass
            
    else:
        # Send text and then delete the result message after 5 minutes
        result_msg = await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))
        
        await asyncio.sleep(300)  # 5 minutes
        try:
            await result_msg.delete()  # Bot ka result delete
            # USER KA SEARCH MESSAGE DELETE HONA CHAHIYE - MOVIE MIL GAYI ✅
            await message.delete()     # USER KA SEARCH MESSAGE DELETE ✅
        except Exception:
            pass
        
    if is_spellcheck_result:
        # Delete the spell-check message (the one showing the options) if it was a result from a callback query
        try:
            await msg.message.delete()
        except Exception:
            pass


async def advantage_spell_chok(msg):
    # Turant reply dena taaki user ko lage bot kaam kar raha hai
    processing_msg = await msg.reply_text('🧐 **Checking spelling...** Please wait ⏳')
    
    query = re.sub(r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|movie|find|send|get|full).*","", msg.text, flags=re.IGNORECASE).strip()
    
    if not query:
        query = msg.text.strip()

    g_s = await search_gagala(query)
    
    # Custom not found message with button
    not_found_msg = """
क्षमा करें,हमें आपकी फ़ाइल नहीं मिली। हो सकता है कि आपने स्पेलिंग सही नही लिखी हो? कृपया सही ढंग से लिखने का प्रयास करें 🙌

SORRY, we haven't find your file. Maybe you made a mistake? Please try to write correctly 😊 

●■●■●■●■●■●■●■

Search other bot
"""
    
    # Create inline button for other bot
    other_bot_button = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 Search Other Bot", url="t.me/asfilter_bot")
    ]])
    
    if not g_s:
        final_msg = await processing_msg.edit_text(
            not_found_msg, 
            reply_markup=other_bot_button
        )
        await asyncio.sleep(120)  # 2 minutes
        try:
            await final_msg.delete()
            # User message delete NAHI karo - NOT FOUND CASE
        except:
            pass
        return

    # Suggestions nikalna
    movielist = []
    gs_parsed = []
    regex = re.compile(r".*(imdb|wikipedia).*", re.IGNORECASE)
    gs = list(filter(regex.match, g_s))
    gs_parsed = [re.sub(
        r'\b(\-([a-zA-Z-\s])\-\simdb|(\-\s)?imdb|(\-\s)?wikipedia|\(|\)|\-|reviews|full|all|episode(s)?|film|movie|series)',
        '', i, flags=re.IGNORECASE) for i in gs]
    if not gs_parsed:
        reg = re.compile(r"watch(\s[a-zA-Z0-9_\s\-\(\)]*)*\|.*", re.IGNORECASE)
        for mv in g_s:
            match = reg.match(mv)
            if match:
                gs_parsed.append(match.group(1))
    
    user = msg.from_user.id if msg.from_user else 0
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
    
    # Stop and send not found message if no movie suggestions found
    if not movielist:
        final_msg = await processing_msg.edit_text(
            not_found_msg, 
            reply_markup=other_bot_button
        )
        await asyncio.sleep(120)  # 2 minutes
        try:
            await final_msg.delete()
            # User message delete NAHI karo - NOT FOUND CASE
        except:
            pass
        return
        
    SPELL_CHECK[msg.id] = movielist
    btn = [[
        InlineKeyboardButton(
            text=movie.strip(),
            callback_data=f"spolling#{user}#{k}",
        )
    ] for k, movie in enumerate(movielist)]
    btn.append([InlineKeyboardButton(text="❌ ᴄʟᴏsᴇ sᴘᴇʟʟ ᴄʜᴇᴄᴋ ❌", callback_data=f'spolling#{user}#close_spellcheck')])
    
    # Edit the processing message to show the spell check options
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
                    await asyncio.sleep(300)
                    try:
                        await result_msg.delete()
                        # USER KA SEARCH MESSAGE DELETE HONA CHAHIYE - MOVIE MIL GAYI ✅
                        await message.delete()
                    except Exception:
                        pass
                    
                except Exception as e:
                    logger.exception(e)
                return True # Return True if manual filter was found and sent
    else:
        return False # Return False if no manual filter was found


async def correct_spelling(search_term):
    """
    Function to correct spelling mistakes in search term
    """
    try:
        # Remove extra spaces
        search_term = ' '.join(search_term.split())
        
        # Common spelling corrections dictionary
        corrections = {
            'avangers': 'avengers',
            'avngers': 'avengers',
            'avenger': 'avengers',
            'intersteller': 'interstellar',
            'interstalar': 'interstellar',
            'inceptionn': 'inception',
            'incepton': 'inception',
            'jumanji': 'jumanji',
            'jumanjee': 'jumanji',
            'harry potterr': 'harry potter',
            'harrypotter': 'harry potter',
            'spider man': 'spider-man',
            'spiderman': 'spider-man',
            'iron man': 'iron man',
            'ironman': 'iron man',
            'bat man': 'batman',
            'super man': 'superman',
            'wonder women': 'wonder woman',
            'wonderwoman': 'wonder woman',
            'fast furious': 'fast & furious',
            'fastandfurious': 'fast & furious',
            'lord rings': 'lord of the rings',
            'lordoftherings': 'lord of the rings',
            'hobbit': 'the hobbit',
            'transformerss': 'transformers',
            'transformes': 'transformers',
            'jurassic park': 'jurassic park',
            'jurrasic': 'jurassic',
            'terminatorr': 'terminator',
            'terminater': 'terminator',
            'matrixx': 'matrix',
            'matrics': 'matrix',
            'titanicc': 'titanic',
            'titanik': 'titanic',
            'avatar': 'avatar',
            'avatarr': 'avatar',
            'frozenn': 'frozen',
            'froozen': 'frozen',
            'moana': 'moana',
            'moan': 'moana',
            'zootopia': 'zootopia',
            'zootpoia': 'zootopia',
            'lion king': 'the lion king',
            'lionking': 'the lion king',
            'aladdin': 'aladdin',
            'aladin': 'aladdin',
            'beauty beast': 'beauty and the beast',
            'beautyandbeast': 'beauty and the beast',
            'toy story': 'toy story',
            'toystory': 'toy story',
            'finding nemo': 'finding nemo',
            'findingnemo': 'finding nemo',
            'shrek': 'shrek',
            'shrek': 'shrek',
        }
        
        # Check if search term needs correction
        lower_term = search_term.lower()
        if lower_term in corrections:
            return corrections[lower_term]
        
        # Try to match with common patterns
        for wrong, correct in corrections.items():
            if wrong in lower_term:
                return correct
        
        # If no correction found, return original
        return search_term
        
    except Exception as e:
        logger.error(f"Spelling correction error: {e}")
        return search_term
