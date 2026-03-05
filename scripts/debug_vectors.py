"""Debug script: inspect kb_vectors collection."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import connect, disconnect, get_db


async def main():
    await connect()
    db = get_db()

    total = await db.kb_vectors.count_documents({})
    print(f"\n=== kb_vectors collection ===")
    print(f"Total documents: {total}")

    if total == 0:
        print("No vectors stored at all. Run a scrape first.")
        await disconnect()
        return

    print("\n=== Vectors per bot_id ===")
    async for doc in db.kb_vectors.aggregate([
        {"$group": {"_id": "$bot_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]):
        print(f"  bot_id={doc['_id']!r}  chunks={doc['count']}")

    print("\n=== Sample document (first) ===")
    sample = await db.kb_vectors.find_one({}, {"embedding": 0})
    if sample:
        sample.pop("_id", None)
        for k, v in sample.items():
            print(f"  {k}: {v!r}")

    print("\n=== Bots in database ===")
    async for bot in db.bots.find({}, {"_id": 1, "name": 1, "slug": 1}):
        print(f"  id={str(bot['_id'])!r}  name={bot.get('name')!r}  slug={bot.get('slug')!r}")

    await disconnect()


asyncio.run(main())
