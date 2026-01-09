from __future__ import annotations

"""
MongoDB connection helpers.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from pymongo import MongoClient
from pymongo.client_session import ClientSession
from pymongo.database import Database

logger = logging.getLogger(__name__)

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        # Import settings lazily to ensure env vars are loaded
        from app.config import settings

        uri = settings.MONGODB_URI
        logger.warning(
            f"=== MONGODB DEBUG === Initializing MongoClient with URI: {uri}"
        )
        _client = MongoClient(uri)
    return _client


def get_database() -> Database:
    # Import settings lazily
    from app.config import settings

    client = get_client()
    return client[settings.MONGODB_DB_NAME]


def get_db():
    db = get_database()
    try:
        yield db
    finally:
        # PyMongo manages connection pooling automatically; nothing to close here.
        pass


@contextmanager
def get_transaction() -> Generator[ClientSession, None, None]:
    """
    Global transaction helper for service-level transactions.

    Use this for operations spanning multiple repositories/collections
    that need atomicity. All operations within the context will be
    committed together or rolled back on failure.

    Usage:
        from app.database.mongo import get_transaction

        with get_transaction() as session:
            repo1.collection.insert_one(doc, session=session)
            repo2.collection.update_one(q, u, session=session)
            # Both committed together

    Note:
        Requires MongoDB Replica Set. Will fail on standalone MongoDB.

    Raises:
        pymongo.errors.PyMongoError: If transaction fails
    """
    client = get_client()
    with client.start_session() as session:
        with session.start_transaction():
            yield session
