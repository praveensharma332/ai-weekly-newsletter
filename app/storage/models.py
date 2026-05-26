from datetime import datetime
import json
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Date
from app.storage.database import Base

class Article(Base):
    """Database model for fetched AI articles and news items."""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    source = Column(String(128), nullable=False)
    url = Column(String(1024), unique=True, index=True, nullable=False)
    publish_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    cleaned_content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    category = Column(String(128), nullable=True)
    hash = Column(String(64), unique=True, index=True, nullable=False)  # deduplication hash
    embedding_json = Column(Text, nullable=True)  # stores all-MiniLM-L6-v2 vector as JSON
    is_used = Column(Boolean, default=False, index=True)  # True once incorporated into a newsletter
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def embedding(self) -> Optional[List[float]]:
        """Parses and returns embedding list of floats."""
        if self.embedding_json:
            try:
                return json.loads(self.embedding_json)
            except Exception:
                return None
        return None

    @embedding.setter
    def embedding(self, val: List[float]) -> None:
        """Serializes embedding float list to JSON string."""
        if val is not None:
            self.embedding_json = json.dumps(val)
        else:
            self.embedding_json = None

    def to_dict(self):
        """Converts model to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "publish_date": self.publish_date.isoformat() if self.publish_date else None,
            "cleaned_content": self.cleaned_content,
            "summary": self.summary,
            "category": self.category,
            "hash": self.hash,
            "is_used": self.is_used,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Newsletter(Base):
    """Database model for generated Weekly Newsletters."""
    __tablename__ = "newsletters"

    id = Column(Integer, primary_key=True, index=True)
    issue_date = Column(Date, unique=True, index=True, nullable=False)
    title = Column(String(512), nullable=False)
    tldr = Column(Text, nullable=False)
    content_markdown = Column(Text, nullable=False)
    content_html = Column(Text, nullable=False)
    raw_json_data = Column(Text, nullable=False)  # full synthesized dict from LLM
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "title": self.title,
            "tldr": self.tldr,
            "content_markdown": self.content_markdown,
            "content_html": self.content_html,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
