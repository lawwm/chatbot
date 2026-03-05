from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client: AsyncIOMotorClient = None
db = None


async def connect():
    global client, db
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client.atome
    await create_indexes()


async def disconnect():
    if client:
        client.close()


async def create_indexes():
    await db.users.create_index("username", unique=True)
    await db.sessions.create_index("session_id", unique=True)
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.bots.create_index("slug", unique=True)
    await db.user_roles.create_index([("user_id", 1), ("bot_id", 1)])
    await db.mistakes.create_index([("bot_id", 1), ("status", 1)])
    # Drop the old unique user_id index if it exists (legacy single-conv-per-user schema)
    try:
        await db.meta_conversations.drop_index("user_id_1")
    except Exception:
        pass
    await db.meta_conversations.create_index("conv_id", unique=True)
    await db.meta_conversations.create_index([("user_id", 1), ("updated_at", -1)])


def get_db():
    return db
