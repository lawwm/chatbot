import logging
from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)


async def retrieve_chunks(bot_id: str, query: str, top_k: int = 10) -> str:
    if not settings.voyage_api_key:
        return ""
    try:
        import voyageai
        client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        result = await client.embed([query], model="voyage-3-lite", input_type="query")
        query_vector = result.embeddings[0]

        db = get_db()

        # --- Diagnostics ---
        total_vectors = await db.kb_vectors.count_documents({})
        bot_vectors = await db.kb_vectors.count_documents({"bot_id": bot_id})
        logger.warning("VECTOR DEBUG — bot=%s | bot_vectors=%d | total_vectors=%d | query=%r",
                       bot_id, bot_vectors, total_vectors, query[:60])
        if bot_vectors == 0:
            logger.warning("VECTOR DEBUG — no vectors stored for this bot. Was a scrape run?")
            return ""

        # Try with filter first
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 150,
                    "limit": top_k,
                    "filter": {"bot_id": {"$eq": bot_id}},
                }
            },
            {"$project": {"text": 1, "score": {"$meta": "vectorSearchScore"}, "_id": 0}},
        ]
        cursor = db.kb_vectors.aggregate(pipeline)
        results = [doc async for doc in cursor]
        chunks = [doc["text"] for doc in results]
        logger.warning("VECTOR DEBUG — filtered search returned %d chunks", len(chunks))
        for i, doc in enumerate(results):
            logger.warning("  [%d] score=%.4f  %s", i, doc.get("score", 0), doc["text"][:80].replace("\n", " "))

        # If filter returned nothing but vectors exist, try without filter (index may lack filter field)
        if not chunks:
            logger.warning("VECTOR DEBUG — retrying WITHOUT filter (Atlas index may not have bot_id as filter field)")
            pipeline_no_filter = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": 50,
                        "limit": top_k,
                    }
                },
                {"$project": {"text": 1, "bot_id": 1, "_id": 0}},
            ]
            cursor2 = db.kb_vectors.aggregate(pipeline_no_filter)
            all_chunks = [doc async for doc in cursor2]
            logger.warning("VECTOR DEBUG — unfiltered search returned %d chunks, bot_ids: %s",
                           len(all_chunks), [c.get("bot_id") for c in all_chunks])
            chunks = [c["text"] for c in all_chunks if c.get("bot_id") == bot_id]
            logger.warning("VECTOR DEBUG — after manual bot_id filter: %d chunks", len(chunks))

        if not chunks:
            return ""
        logger.warning("Retrieved %d chunks for bot=%s query=%r", len(chunks), bot_id, query[:60])
        for i, chunk in enumerate(chunks):
            logger.warning("  chunk[%d]: %s", i, chunk[:120].replace("\n", " "))
        return "\n\n---\n\n".join(chunks)
    except Exception as e:
        logger.error("retrieve_chunks failed for bot=%s: %s", bot_id, e)
        return ""
