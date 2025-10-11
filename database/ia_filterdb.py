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

# Helper function (Assuming this was present in the original bot logic)
def unpack_new_file_id(new_file_id):
    """Unpacks a file id to get the file_id and file_ref."""
    if not isinstance(new_file_id, FileId):
        new_file_id = FileId.decode(new_file_id)
    
    file_id = "{}_{}".format(new_file_id.media_type.value, base64.urlsafe_b64encode(pack('<i', new_file_id.file_unique_id)).decode().rstrip("=").strip())
    
    # file_ref will be the full file_id used for getting the file back from Telegram
    file_ref = new_file_id.file_id
    
    return file_id, file_ref

# --------------------------------------------------------------------------------------
# DATABASE FUNCTIONS
# --------------------------------------------------------------------------------------

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
        # If query is empty, match any file
        raw_pattern = r'.' 
    elif ' ' not in query:
        # Search for query word with boundaries
        # Note: Added '|' and improved regex for better word boundary matching
        raw_pattern = r'(\b|[\.\+\-_]|^)' + re.escape(query) + r'(\b|[\.\+\-_]|$)' 
    else:
        # Search for space-separated words, allowing non-word characters in between
        # This will search for the entire phrase as an approximate match
        raw_pattern = '.*'.join(re.escape(q) for q in query.split())
    
    try:
        # Escape the regex special characters in raw_pattern before compiling
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except Exception as e:
        logger.error(f"Regex compilation error: {e}")
        return [], 0, 0

    # Base filter searches in file_name or caption
    if USE_CAPTION_FILTER:
        # For base search, we use the original logic for file_name OR caption
        base_filter_search = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        base_filter_search = {'file_name': regex}

    if file_type:
        base_filter_search['file_type'] = file_type

    # Combined list of regex patterns for all filters (language, quality, season)
    filter_patterns = []

    if language:
        # Match language name with word boundaries
        # Use a more flexible regex for filter checks
        filter_patterns.append(r'(\b|[\.\+\-_\/]|^)' + re.escape(language) + r'(\b|[\.\+\-_\/]|$)')

    if quality:
        # Match quality/rip name with word boundaries
        filter_patterns.append(r'(\b|[\.\+\-_\/]|^)' + re.escape(quality) + r'(\b|[\.\+\-_\/]|$)')
    
    if season:
        # Match season name (e.g., S01, S1) with word boundaries
        filter_patterns.append(r'(\b|[\.\+\-_\/]|^)' + re.escape(season) + r'(\b|[\.\+\-_\/]|$)')

    # If any filters are applied, modify the filter
    if filter_patterns:
        # Start with the base search filter
        combined_filter_list = [base_filter_search]
        
        # Additional filters MUST be in the file_name (to avoid slow caption searches)
        for pattern in filter_patterns:
            try:
                # Add each filter as a separate regex condition on file_name
                combined_filter_list.append({'file_name': {'$regex': re.compile(pattern, flags=re.IGNORECASE)}})
            except Exception as e:
                logger.error(f"Filter Regex compilation error: {e}")
                # If a filter regex fails, skip it or return empty results based on required strictness
                continue
        
        # Combine all conditions with $and
        final_filter = {'$and': combined_filter_list}
    else:
        # No filters, use the base search filter
        final_filter = base_filter_search


    total_results = await Media.count_documents(final_filter)
    next_offset = offset + max_results

    if next_offset >= total_results:
        next_offset = 0

    cursor = Media.find(final_filter)
    cursor.sort('$natural', -1)
    cursor.skip(offset).limit(max_results)
    files = await cursor.to_list(length=max_results)

    return files, next_offset, total_results


async def get_file_details(query):
    """
    Get file details from database using file_id (_id field).
    This function was missing its indented body, causing the IndentationError.
    """
    return await Media.find_one({'_id': query})


async def delete_file(query):
    """Delete file from database using file_id (_id field)."""
    return await Media.delete_one({'_id': query})
