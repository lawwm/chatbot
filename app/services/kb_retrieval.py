import logging
from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)


async def retrieve_chunks(bot_id: str, query: str, top_k: int = 5) -> str:
    if not settings.voyage_api_key:
        return ""
    try:
        import voyageai
        client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        result = await client.embed([query], model="voyage-3-lite", input_type="query")
        query_vector = result.embeddings[0]

        db = get_db()
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "kb_vectors_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 50,
                    "limit": top_k,
                    "filter": {"bot_id": bot_id},
                }
            },
            {"$project": {"text": 1, "_id": 0}},
        ]
        cursor = db.kb_vectors.aggregate(pipeline)
        chunks = [doc["text"] async for doc in cursor]
        if not chunks:
            logger.info("Vector search returned no results for bot=%s", bot_id)
            return ""
        logger.info("Retrieved %d chunks for bot=%s query=%r", len(chunks), bot_id, query[:60])
        return "\n\n---\n\n".join(chunks)
    except Exception as e:
        logger.error("retrieve_chunks failed for bot=%s: %s", bot_id, e)
        return ""
