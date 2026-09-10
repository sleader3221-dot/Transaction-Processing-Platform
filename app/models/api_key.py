from sqlalchemy import Column, String, Boolean, DateTime, text
from app.db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(26), primary_key=True)
    client_id = Column(String(255), nullable=False, unique=True)
    key_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))
