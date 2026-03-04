"""Delete all user accounts and their sessions from the database."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings


async def main():
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client.get_default_database()

    users = await db.users.count_documents({})
    sessions = await db.sessions.count_documents({})
    print(f"Found {users} user(s) and {sessions} session(s).")

    confirm = input("Delete all? (yes/no): ")
    if confirm.lower() != "yes":
        print("Aborted.")
        return

    await db.users.delete_many({})
    await db.sessions.delete_many({})
    print("Done.")
    client.close()


asyncio.run(main())
