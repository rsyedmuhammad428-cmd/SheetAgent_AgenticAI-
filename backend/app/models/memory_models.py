"""
Memory Models — Phase 4
Tables:
  - user_preferences   : format, currency, chart style, excel theme
  - session_history    : past sessions with schema + output metadata
  - memory_snippets    : key facts Gemini learned about the user's data patterns
"""
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, Float, Boolean
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default="default")

    # Format preferences
    date_format     = Column(String, default="YYYY-MM-DD")
    currency        = Column(String, default="USD")
    currency_symbol = Column(String, default="$")
    number_locale   = Column(String, default="en-US")

    # Excel preferences
    excel_theme     = Column(String, default="professional")   # professional / minimal / colorful
    header_color    = Column(String, default="1F4E79")
    font_name       = Column(String, default="Calibri")
    font_size       = Column(Integer, default=11)
    freeze_header   = Column(Boolean, default=True)
    auto_filter     = Column(Boolean, default=True)

    # Chart preferences
    chart_style     = Column(String, default="bar")            # bar / line / pie
    chart_colorset  = Column(String, default="blue")

    # Workflow preferences
    always_generate_summary   = Column(Boolean, default=True)
    always_generate_charts    = Column(Boolean, default=False)
    auto_approve_cleaning     = Column(Boolean, default=False)
    preferred_schema_handling = Column(String, default="auto")

    # Raw JSON for arbitrary extras
    extras = Column(JSON, default={})

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SessionHistory(Base):
    __tablename__ = "session_history"

    id            = Column(String, primary_key=True)
    file_name     = Column(String)
    file_type     = Column(String)
    schema_type   = Column(String)
    row_count     = Column(Integer, default=0)
    col_count     = Column(Integer, default=0)
    status        = Column(String, default="complete")
    output_path   = Column(String, nullable=True)
    plan_steps    = Column(JSON, default=[])
    column_names  = Column(JSON, default=[])
    quality_score = Column(Float, nullable=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class MemorySnippet(Base):
    __tablename__ = "memory_snippets"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    key        = Column(String, index=True)   # e.g. "preferred_date_format", "common_schema"
    value      = Column(Text)
    source     = Column(String, default="inferred")  # "inferred" | "explicit"
    confidence = Column(Float, default=0.8)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

