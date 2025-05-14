from typing import Generator
from sqlalchemy import Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session,scoped_session,sessionmaker
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)

    messages = relationship("Message", back_populates="user")


class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    message = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)

    # 對應到 User 的關聯
    user = relationship("User", back_populates="messages")


# 建立 SQLite engine
engine = create_engine("sqlite:///example.db")
SessionLocal = scoped_session(sessionmaker(bind=engine)) 
# 檢查是否有表格，若沒有就建立
Base.metadata.create_all(engine)

def get_db() -> Generator[Session, None, None]:
    """FastAPI 和 Flask 通用的 DB Session 產生器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()