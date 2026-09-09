import asyncio
import hashlib
import secrets
import sys

from app.db.database import AsyncSessionLocal
from app.models.api_key import ApiKey
from app.core.id_gen import generate_id


async def create(client_id: str) -> None:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    async with AsyncSessionLocal() as db:
        db.add(ApiKey(id=generate_id(), client_id=client_id,
                      key_hash=key_hash, is_active=True))
        await db.commit()

    print(f"\nClient ID : {client_id}")
    print(f"API Key   : {raw_key}")
    print("Store this key now - it will not be shown again.\n")


if __name__ == "__main__":
    client = sys.argv[1] if len(sys.argv) > 1 else "default"
    asyncio.run(create(client))