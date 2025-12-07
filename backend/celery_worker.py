from celery import Celery
import os
from .llm import get_embedding
from .search import index_document
from .models import SessionLocal, DocumentModel, ChatDocumentModel

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

celery_app = Celery(
    "worker",
    broker=f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:5672//",
    backend=f"rpc://"
)


from .database import get_redis_client

@celery_app.task(name="process_document")
def process_document(es_doc_id, content, filename, uploaded_by=None, chat_id=None):
    """Process document: generate embedding and index to ES.
    
    Args:
        es_doc_id: string id to use in Elasticsearch
        content: full text content
        filename: original filename
        uploaded_by: (Deprecated) handled in main API
        chat_id: (Deprecated) handled in main API
    """
    print(f"Processing document: {filename} ({es_doc_id})")

    # 1. Generate Embedding
    embedding = get_embedding(content)

    # 2. Index to Elasticsearch
    metadata = {"filename": filename}
    index_document(es_doc_id, content, embedding, metadata)
    
    # 3. Update Status in Redis
    try:
        redis_client = get_redis_client()
        if redis_client:
            # Mark as ready. We can expire this after some time or keep it.
            # For simplicity, let's keep it for 24 hours so UI can show "Ready"
            redis_client.setex(f"doc_status:{es_doc_id}", 86400, "ready")
            print(f"Updated Redis status for {es_doc_id} to 'ready'")
        else:
            print(f"Warning: Redis client not available, could not update status for {es_doc_id}")
    except Exception as e:
        print(f"Error updating redis status: {e}")

    return f"Document {filename} processed and indexed."
