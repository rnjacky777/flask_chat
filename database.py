from typing import Generator
from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, create_engine
from sqlalchemy.orm import relationship, Session, scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

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
    timestamp = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="messages")


# 建立 SQLite engine
engine = create_engine("sqlite:///example.db")
SessionLocal = scoped_session(sessionmaker(bind=engine))

Base.metadata.create_all(engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
