"""Google Cloud Firestore Synchronization & Cloud Persistence Engine for Aevum Core.

Provides bidirectional synchronization between local/ephemeral SQLite storage
and durable Google Cloud Firestore:
1. Real-time background write sync for messages, conversations, memories, relationships, and character persona.
2. Automatic startup hydration: When running on ephemeral cloud containers (e.g. Render) with an
   empty database, automatically re-populates SQLite from Firestore in seconds.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_firestore_client = None
_initialized = False


def get_firestore_client():
    """Lazily initialize and return the Firestore client singleton."""
    global _firestore_client, _initialized
    if _initialized:
        return _firestore_client

    _initialized = True
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if firebase_admin._apps:
            _firestore_client = firestore.client()
            return _firestore_client

        # 1. Check for raw JSON string in environment (ideal for Render cloud deployments)
        raw_json = os.environ.get("FIREBASE_CREDENTIALS_JSON", "").strip()
        if raw_json:
            try:
                cred_dict = json.loads(raw_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                _firestore_client = firestore.client()
                logger.info("Firestore initialized via FIREBASE_CREDENTIALS_JSON.")
                return _firestore_client
            except Exception as e:
                logger.error("Failed to parse FIREBASE_CREDENTIALS_JSON: %s", e)

        # 2. Check for key file path
        key_candidates = [
            os.environ.get("FIREBASE_CREDENTIALS_PATH", ""),
            "firebase-key.json",
            "backend/firebase-key.json",
            str(Path(__file__).resolve().parents[2] / "firebase-key.json"),
            str(Path(__file__).resolve().parents[3] / "firebase-key.json"),
        ]

        for cand in key_candidates:
            if cand and Path(cand).exists():
                cred = credentials.Certificate(str(cand))
                firebase_admin.initialize_app(cred)
                _firestore_client = firestore.client()
                logger.info("Firestore initialized via file %s.", cand)
                return _firestore_client

        logger.info("No Firebase credentials configured; Firestore sync is disabled.")
    except Exception as e:
        logger.warning("Could not initialize Firestore client: %s", e)

    return None


def is_firestore_enabled() -> bool:
    """Check if Firestore client is active and usable."""
    from app.core.config import settings
    if getattr(settings, "environment", "") == "test":
        return False
    return get_firestore_client() is not None



def sync_message_to_firestore(
    message_id: str,
    conversation_id: str,
    role: str,
    content: str,
    created_at: Any = None,
) -> None:
    """Persist a message document to Firestore."""
    if not is_firestore_enabled():
        return
    client = get_firestore_client()

    try:
        from firebase_admin import firestore

        ts_str = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or datetime.now(timezone.utc).isoformat())
        doc_ref = client.collection("messages").document(str(message_id))
        doc_ref.set({
            "id": str(message_id),
            "conversation_id": str(conversation_id),
            "role": str(role),
            "content": str(content),
            "created_at": ts_str,
            "synced_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        # Also touch conversation updated_at in Firestore
        conv_ref = client.collection("conversations").document(str(conversation_id))
        conv_ref.set({
            "id": str(conversation_id),
            "updated_at": ts_str,
            "last_message": str(content[:100]),
            "synced_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)
    except Exception as e:
        logger.warning("Failed to sync message %s to Firestore: %s", message_id, e)


def sync_relationship_to_firestore(
    user_id: str = "user",
    affection: float = 0.68,
    familiarity: float = 0.72,
    trust: float = 0.70,
    comfort: float = 0.65,
    attachment: float = 0.50,
    respect: float = 0.80,
    version: int = 1,
) -> None:
    """Persist relationship metrics to Firestore."""
    if not is_firestore_enabled():
        return
    client = get_firestore_client()

    try:
        from firebase_admin import firestore

        doc_ref = client.collection("relationships").document(str(user_id))
        doc_ref.set({
            "id": str(user_id),
            "user_id": str(user_id),
            "affection": float(affection),
            "familiarity": float(familiarity),
            "trust": float(trust),
            "comfort": float(comfort),
            "attachment": float(attachment),
            "respect": float(respect),
            "version": int(version),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)
    except Exception as e:
        logger.warning("Failed to sync relationship to Firestore: %s", e)


def sync_character_to_firestore(
    character_id: str = "aevum",
    name: str = "苏棠",
    age: int = 22,
    occupation: str = "计算机系大四学生 / 独立游戏开发者",
    background: str = "",
    personality_traits: Optional[list[dict]] = None,
) -> None:
    """Persist character persona to Firestore."""
    if not is_firestore_enabled():
        return
    client = get_firestore_client()

    try:
        from firebase_admin import firestore

        doc_ref = client.collection("character_definitions").document(str(character_id))
        data = {
            "id": str(character_id),
            "name": name,
            "age": age,
            "occupation": occupation,
            "background": background,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if personality_traits is not None:
            data["personality_traits"] = personality_traits

        doc_ref.set(data, merge=True)
    except Exception as e:
        logger.warning("Failed to sync character %s to Firestore: %s", character_id, e)


async def hydrate_sqlite_if_empty(session) -> int:
    """Check if SQLite is empty; if so, populate from Firestore.
    
    Returns the count of restored messages.
    """
    client = get_firestore_client()
    if not client:
        return 0

    try:
        from sqlalchemy import func, select
        from app.db.models import Conversation, Message, RelationshipRecord, CharacterDefinitionRecord

        # Check local message count
        stmt = select(func.count(Message.id))
        result = await session.execute(stmt)
        local_count = result.scalar_one()

        if local_count > 0:
            logger.info("Local SQLite already contains %d messages; skipping initial hydration.", local_count)
            return 0

        logger.info("Local SQLite is empty! Hydrating all data from Google Cloud Firestore...")

        # 1. Hydrate conversations
        conv_docs = client.collection("conversations").stream()
        for doc in conv_docs:
            d = doc.to_dict()
            c_id = d.get("id") or doc.id
            created_at = datetime.fromisoformat(d["created_at"]) if "created_at" in d and isinstance(d["created_at"], str) else datetime.now(timezone.utc)
            updated_at = datetime.fromisoformat(d["updated_at"]) if "updated_at" in d and isinstance(d["updated_at"], str) else created_at
            conv = Conversation(id=c_id, created_at=created_at, updated_at=updated_at)
            session.add(conv)

        await session.flush()

        # 2. Hydrate messages
        msg_docs = client.collection("messages").order_by("created_at").stream()
        restored_msgs = 0
        for doc in msg_docs:
            d = doc.to_dict()
            m_id = d.get("id") or doc.id
            created_at = datetime.fromisoformat(d["created_at"]) if "created_at" in d and isinstance(d["created_at"], str) else datetime.now(timezone.utc)
            msg = Message(
                id=m_id,
                conversation_id=d.get("conversation_id"),
                role=d.get("role", "user"),
                content=d.get("content", ""),
                created_at=created_at,
            )
            session.add(msg)
            restored_msgs += 1

        # 3. Hydrate relationship
        rel_doc = client.collection("relationships").document("user").get()
        if rel_doc.exists:
            rd = rel_doc.to_dict()
            rel_rec = RelationshipRecord(
                id="user",
                user_id="user",
                version=rd.get("version", 1),
                trust=rd.get("trust", 0.70),
                familiarity=rd.get("familiarity", 0.72),
                comfort=rd.get("comfort", 0.65),
                affection=rd.get("affection", 0.68),
                attachment=rd.get("attachment", 0.50),
                respect=rd.get("respect", 0.80),
            )
            session.add(rel_rec)

        # 4. Hydrate character definition
        char_doc = client.collection("character_definitions").document("aevum").get()
        if char_doc.exists:
            cd = char_doc.to_dict()
            char_rec = CharacterDefinitionRecord(
                id="aevum",
                version=1,
                name=cd.get("name", "苏棠"),
                age=cd.get("age", 22),
                occupation=cd.get("occupation", "计算机系大四学生 / 独立游戏开发者"),
                background=cd.get("background", ""),
            )
            session.add(char_rec)

        await session.commit()
        logger.info("Successfully hydrated %d messages and character data from Firestore!", restored_msgs)
        return restored_msgs
    except Exception as e:
        logger.error("Failed to hydrate SQLite from Firestore: %s", e)
        await session.rollback()
        return 0
