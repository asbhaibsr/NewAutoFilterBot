# users_chats_db.py 

# https://github.com/odysseusmax/animated-lamp/blob/master/bot/database/database.py
import motor.motor_asyncio
from datetime import datetime, timedelta
from info import DATABASE_NAME, DATABASE_URI, IMDB, IMDB_TEMPLATE, MELCOW_NEW_USERS, P_TTI_SHOW_OFF, SINGLE_BUTTON, SPELL_CHECK_REPLY, PROTECT_CONTENT

class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.grp = self.db.groups


    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            ban_status=dict(
                is_banned=False,
                ban_reason="",
            ),
            verification=dict(
                is_verified=False,
                last_verified=None,
            ),
            premium=dict(
                is_premium=False,
                plan_type=None,
                premium_since=None,
                premium_expiry=None
            )
        )


    def new_group(self, id, title):
        return dict(
            id = id,
            title = title,
            chat_status=dict(
                is_disabled=False,
                reason="",
            ),
        )
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)
    
    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count
    
    async def remove_ban(self, id):
        ban_status = dict(
            is_banned=False,
            ban_reason=''
        )
        await self.col.update_one({'id': id}, {'$set': {'ban_status': ban_status}})
    
    async def ban_user(self, user_id, ban_reason="No Reason"):
        ban_status = dict(
            is_banned=True,
            ban_reason=ban_reason
        )
        await self.col.update_one({'id': user_id}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = dict(
            is_banned=False,
            ban_reason=''
        )
        user = await self.col.find_one({'id':int(id)})
        if not user:
            return default
        return user.get('ban_status', default)

    async def get_all_users(self):
        return self.col.find({})
    

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})


    async def get_banned(self):
        users = self.col.find({'ban_status.is_banned': True})
        chats = self.grp.find({'chat_status.is_disabled': True})
        b_chats = [chat['id'] async for chat in chats]
        b_users = [user['id'] async for user in users]
        return b_users, b_chats
    
    # Verification Methods
    async def mark_user_verified(self, user_id):
        """Mark user as verified for 24 hours"""
        verification_data = {
            'verification.is_verified': True,
            'verification.last_verified': datetime.now()
        }
        await self.col.update_one(
            {'id': user_id}, 
            {'$set': verification_data}
        )
    
    async def check_verification_status(self, user_id):
        """Check if user is verified (within 24 hours)"""
        user = await self.col.find_one({'id': user_id})
        if not user:
            return False
            
        verification = user.get('verification', {})
        if verification.get('is_verified'):
            last_verified = verification.get('last_verified')
            if last_verified:
                # Check if verification is within 24 hours
                if isinstance(last_verified, datetime):
                    time_diff = datetime.now() - last_verified
                    if time_diff.total_seconds() < 86400:  # 24 hours
                        return True
                    else:
                        # Verification expired
                        await self.col.update_one(
                            {'id': user_id},
                            {'$set': {'verification.is_verified': False}}
                        )
        return False

    # Premium Methods
    async def add_premium_user(self, user_id, plan_type):
        """Add user to premium"""
        expiry_time = self.calculate_premium_expiry(plan_type)
        premium_data = {
            'premium.is_premium': True,
            'premium.plan_type': plan_type,
            'premium.premium_since': datetime.now(),
            'premium.premium_expiry': expiry_time
        }
        await self.col.update_one(
            {'id': user_id}, 
            {'$set': premium_data},
            upsert=True
        )
        return expiry_time

    async def remove_premium_user(self, user_id):
        """Remove user from premium"""
        premium_data = {
            'premium.is_premium': False,
            'premium.plan_type': None,
            'premium.premium_since': None,
            'premium.premium_expiry': None
        }
        await self.col.update_one(
            {'id': user_id}, 
            {'$set': premium_data}
        )

    async def get_premium_status(self, user_id):
        """Get user's premium status"""
        user = await self.col.find_one({'id': user_id})
        if user and user.get('premium', {}).get('is_premium'):
            expiry = user['premium'].get('premium_expiry')
            if expiry and expiry > datetime.now():
                return {
                    'is_premium': True,
                    'plan': user['premium'].get('plan_type'),
                    'expiry': expiry
                }
            else:
                # Premium expired
                await self.remove_premium_user(user_id)
        return {'is_premium': False}

    def calculate_premium_expiry(self, plan_type):
        """Calculate premium expiry time"""
        plan_durations = {
            '1day': timedelta(days=1),
            '1month': timedelta(days=30),
            '1year': timedelta(days=365)
        }
        return datetime.now() + plan_durations.get(plan_type, timedelta(days=1))

    async def add_chat(self, chat, title):
        chat = self.new_group(chat, title)
        await self.grp.insert_one(chat)
    

    async def get_chat(self, chat):
        chat = await self.grp.find_one({'id':int(chat)})
        return False if not chat else chat.get('chat_status')
    

    async def re_enable_chat(self, id):
        chat_status=dict(
            is_disabled=False,
            reason="",
            )
        await self.grp.update_one({'id': int(id)}, {'$set': {'chat_status': chat_status}})
        
    async def update_settings(self, id, settings):
        await self.grp.update_one({'id': int(id)}, {'$set': {'settings': settings}})
        
    
    async def get_settings(self, id):
        default = {
            'button': SINGLE_BUTTON,
            'botpm': P_TTI_SHOW_OFF,
            'file_secure': PROTECT_CONTENT,
            'imdb': IMDB,
            'spell_check': SPELL_CHECK_REPLY,
            'welcome': MELCOW_NEW_USERS,
            'template': IMDB_TEMPLATE
        }
        chat = await self.grp.find_one({'id':int(id)})
        if chat:
            return chat.get('settings', default)
        return default
    

    async def disable_chat(self, chat, reason="No Reason"):
        chat_status=dict(
            is_disabled=True,
            reason=reason,
            )
        await self.grp.update_one({'id': int(chat)}, {'$set': {'chat_status': chat_status}})
    

    async def total_chat_count(self):
        count = await self.grp.count_documents({})
        return count
    

    async def get_all_chats(self):
        return self.grp.find({})


    async def get_db_size(self):
        return (await self.db.command("dbstats"))['dataSize']


db = Database(DATABASE_URI, DATABASE_NAME)
