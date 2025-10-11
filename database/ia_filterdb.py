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

    # TODO: Find better way to get same file_id for same media to avoid duplicates
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


async def get_search_results(query, file_type=None, max_results=10, offset=0, filter=False, language=None, quality=None, season=None):
    """For given query return (results, next_offset)"""

    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        # Search for query word with boundaries
        raw_pattern = r'(\b|[\.\+\-_])' + re.escape(query) + r'(\b|[\.\+\-_])' 
    else:
        # Search for space-separated words, allowing non-word characters in between
        raw_pattern = '.*'.join(re.escape(q) for q in query.split())
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return [], 0, 0

    # Base filter searches in file_name or caption
    if USE_CAPTION_FILTER:
        base_filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        base_filter = {'file_name': regex}

    if file_type:
        base_filter['file_type'] = file_type

    # NEW: Apply additional filters for language, quality, and season
    
    # Combined list of regex patterns for all filters (language, quality, season)
    filter_patterns = []

    if language:
        # Match language name with word boundaries
        filter_patterns.append(r'(\b|[\.\+\-_])' + re.escape(language) + r'(\b|[\.\+\-_])')

    if quality:
        # Match quality/rip name with word boundaries
        filter_patterns.append(r'(\b|[\.\+\-_])' + re.escape(quality) + r'(\b|[\.\+\-_])')
    
    if season:
        # Match season name (e.g., S01, S1) with word boundaries
        filter_patterns.append(r'(\b|[\.\+\-_])' + re.escape(season) + r'(\b|[\.\+\-_])')

    # If any filters are applied, modify the base filter to ensure all patterns exist in file_name
    if filter_patterns:
        # Create an $and query for the combined search and filter patterns
        
        # 1. Base search (file_name or caption)
        combined_filter = [base_filter]
        
        # 2. Additional filters (must be in file_name)
        for pattern in filter_patterns:
            combined_filter.append({'file_name': {'$regex': re.compile(pattern, flags=re.IGNORECASE)}})
        
        filter = {'$and': combined_filter}
    else:
        filter = base_filter


    total_results = await Media.count_documents(filter)
    next_offset = offset + max_results

    if next_offset >= total_results:
        next_offset = 0

    cursor = Media.find(filter)
    cursor.sort('$natural', -1)
    cursor.skip(offset).limit(max_results)
    files = await cursor.to_list(length=max_results)

    return files, next_offset, total_results


async def get_file_details(query):
# ... (rest of the file remains the same)
