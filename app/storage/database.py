import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from app.config.settings import settings

logger = logging.getLogger("newsletter.storage.database")

# Generate engine URL
SQLALCHEMY_DATABASE_URL = f"sqlite:///{settings.DB_PATH.resolve()}"

# Create SQLite engine
# Use check_same_thread=False for thread safety in multi-threaded / FastAPI setups
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# Thread-safe session registry
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(session_factory)

Base = declarative_base()

def init_db() -> None:
    """Initializes SQLite database tables."""
    try:
        # Import models here to ensure they register on Base metadata
        import app.storage.models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info(f"Database initialized successfully at {settings.DB_PATH}")
    except Exception as e:
        logger.critical(f"Failed to initialize SQLite database: {e}")
        raise
