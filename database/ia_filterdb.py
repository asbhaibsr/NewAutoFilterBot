import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import DATABASE_URI, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]
instance = Instance.from_db(db)

@instance.register
class Media(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)

    class Meta:
        indexes = ('$file_name', )
        collection_name = COLLECTION_NAME

async def save_file(media):
    """Save file in database"""
    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
    try:
        file = Media(
            file_id=file_id,
            file_ref=file_ref,
            file_name=file_name,
            file_size=media.file_size,
            file_type=media.file_type,
            mime_type=media.mime_type,
            caption=media.caption.html if media.caption else None,
        )
    except ValidationError:
        logger.exception('Error occurred while saving file in database')
        return False, 2
    else:
        try:
            await file.commit()
        except DuplicateKeyError:      
            logger.warning(
                f'{getattr(media, "file_name", "NO_FILE")} is already saved in database'
            )
            return False, 0
        else:
            logger.info(f'{getattr(media, "file_name", "NO_FILE")} is saved to database')
            return True, 1

async def get_search_results(query, file_type=None, max_results=10, offset=0, filter=False):
    """Optimized search function with better performance"""
    start_time = time.time()
    query = query.strip().lower()
    
    if not query:
        return [], '', 0
    
    # Create search pattern for better matching
    if ' ' not in query:
        # Single word search - use word boundaries
        pattern = f'\\b{re.escape(query)}\\b'
    else:
        # Multiple words - allow partial matches with word boundaries
        words = query.split()
        pattern = '.*'.join([f'\\b{re.escape(word)}' for word in words])
    
    try:
        regex = re.compile(pattern, flags=re.IGNORECASE)
    except re.error:
        # Fallback to simple search if regex fails
        regex = re.compile(re.escape(query), flags=re.IGNORECASE)
    
    # Build filter with optimized query
    if USE_CAPTION_FILTER:
        search_filter = {
            '$or': [
                {'file_name': {'$regex': regex}},
                {'caption': {'$regex': regex}}
            ]
        }
    else:
        search_filter = {'file_name': {'$regex': regex}}
    
    if file_type:
        search_filter['file_type'] = file_type
    
    # Get total count
    total_results = await Media.count_documents(search_filter)
    
    # Calculate next offset
    next_offset = offset + max_results
    if next_offset >= total_results:
        next_offset = ''
    
    # Execute query with optimization
    cursor = Media.find(search_filter)
    cursor.sort('$natural', -1)
    cursor.skip(offset).limit(max_results)
    
    files = await cursor.to_list(length=max_results)
    
    end_time = time.time()
    logger.info(f"Search for '{query}' took {end_time - start_time:.2f} seconds, found {len(files)} results")
    
    return files, next_offset, total_results

async def get_file_details(query):
    """Get file details by file_id"""
    search_filter = {'file_id': query}
    cursor = Media.find(search_filter)
    filedetails = await cursor.to_list(length=1)
    return filedetails

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    """Return file_id, file_ref"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_re
