from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # "user" or "admin"
    credits = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("Task", back_populates="user")
    credit_transactions = relationship("CreditTransaction", back_populates="user")


class LLMConfig(Base):
    __tablename__ = "llm_configs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)  # "openai", "anthropic", "volcano"
    api_key = Column(String(1000), nullable=False)
    model_name = Column(String(100), nullable=False)
    base_url = Column(String(500), nullable=True)
    agent_type = Column(String(50), nullable=False)  # "strategy", "brand", "operations", "all"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentKnowledge(Base):
    __tablename__ = "agent_knowledge"
    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(String(50), nullable=False)  # "strategy", "brand", "operations"
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    query = Column(Text, nullable=False)
    agents_selected = Column(JSON)  # list: ["strategy","brand","operations"]
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    brand_name = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="tasks")
    results = relationship("TaskResult", back_populates="task", cascade="all, delete-orphan")


class TaskResult(Base):
    __tablename__ = "task_results"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    agent_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(20), nullable=True)  # "md", "pdf", "png"
    file_name = Column(String(200), nullable=True)
    download_credits = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="results")


class SystemSetting(Base):
    """
    Simple key/value store for runtime configuration (PPT provider selection,
    external API keys, endpoints). Values are JSON-encoded in the `value` column.
    """
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=True)          # JSON-encoded
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False)
    task_result_id = Column(Integer, ForeignKey("task_results.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="credit_transactions")
