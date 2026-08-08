from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class FormAnalysis(Base):
    """An analysis session against a target (xwa-sdk Analysis)."""

    __tablename__ = "form_analyses"
    id = Column(Integer, primary_key=True, index=True)
    target = Column(String, index=True)
    status = Column(String, default="RUNNING")  # RUNNING, COMPLETED, ERROR
    analysis_type = Column(String, default="form_scan")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    forms = relationship("Form", back_populates="analysis", cascade="all, delete-orphan")
    oauth_flows = relationship("OAuthFlow", back_populates="analysis", cascade="all, delete-orphan")
    session_cookies = relationship("SessionCookie", back_populates="analysis", cascade="all, delete-orphan")


class Form(Base):
    __tablename__ = "forms"
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("form_analyses.id", ondelete="CASCADE"))

    page_url = Column(Text, nullable=True)
    action = Column(Text, nullable=True)
    method = Column(String, default="GET")
    enctype = Column(String, nullable=True)
    is_secure = Column(Integer, default=0)  # action targets https
    redirect_chain = Column(Text, nullable=True)  # JSON array of {url, status}

    fields = relationship("FormField", back_populates="form", cascade="all, delete-orphan")
    analysis = relationship("FormAnalysis", back_populates="forms")


class FormField(Base):
    __tablename__ = "form_fields"
    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id", ondelete="CASCADE"))

    name = Column(String, nullable=True)
    input_type = Column(String, nullable=True)  # text, password, email, hidden, ...
    value = Column(Text, nullable=True)  # initial value (hidden fields may carry tokens)
    required = Column(Integer, default=0)
    autocomplete = Column(String, nullable=True)
    placeholder = Column(String, nullable=True)
    is_csrf = Column(Integer, default=0)  # token-like hidden field

    form = relationship("Form", back_populates="fields")


class OAuthFlow(Base):
    __tablename__ = "oauth_flows"
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("form_analyses.id", ondelete="CASCADE"))

    endpoint = Column(Text, nullable=True)
    flow_type = Column(String, nullable=True)  # authorization_code, implicit, oidc, unknown
    client_id = Column(String, nullable=True)
    redirect_uri = Column(Text, nullable=True)
    scope = Column(Text, nullable=True)
    uses_state = Column(Integer, default=0)
    weakness = Column(Text, nullable=True)  # comma-separated findings

    analysis = relationship("FormAnalysis", back_populates="oauth_flows")


class SessionCookie(Base):
    __tablename__ = "session_cookies"
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("form_analyses.id", ondelete="CASCADE"))

    name = Column(String, nullable=True)
    value_preview = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    path = Column(String, nullable=True)
    http_only = Column(Integer, default=0)
    secure = Column(Integer, default=0)
    same_site = Column(String, nullable=True)  # Strict, Lax, None, None
    max_age = Column(String, nullable=True)

    analysis = relationship("FormAnalysis", back_populates="session_cookies")
