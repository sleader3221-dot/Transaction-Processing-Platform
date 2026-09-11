import asyncio
import argparse
import hashlib
import secrets
import sys

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.api_key import ApiKey
from app.core.id_gen import generate_id


async def create(client_id: str) -> None:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(ApiKey).where(ApiKey.client_id == client_id)
        )).scalar_one_or_none()
        if existing:
            existing.key_hash = key_hash
            existing.is_active = True
        else:
            db.add(ApiKey(id=generate_id(), client_id=client_id,
                          key_hash=key_hash, is_active=True))
        await db.commit()

    print(f"\nClient ID : {client_id}")
    print(f"API Key   : {raw_key}")
    print("Store this key now - it will not be shown again.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an API key")
    parser.add_argument("client_id", nargs="?", help="Client identifier")
    parser.add_argument("--name", dest="name", help="Client identifier")
    args = parser.parse_args()
    client = args.name or args.client_id or "default"
    asyncio.run(create(client))