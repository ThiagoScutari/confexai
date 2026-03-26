import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer,
    Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class JobType(str, enum.Enum):
    background_removal = "background_removal"
    protected_region_detection = "protected_region_detection"
    color_variation = "color_variation"
    background_alternative = "background_alternative"
    seo_description = "seo_description"
    video_ugc = "video_ugc"


class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    fabric = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = relationship("ProductImage", back_populates="product")
    seo_descriptions = relationship("SEODescription", back_populates="product")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    type = Column(String(50), nullable=False)  # original | color_variant | background | video
    original_url = Column(String(500), nullable=True)
    processed_url = Column(String(500), nullable=True)
    color_hex = Column(String(7), nullable=True)
    background_type = Column(String(50), nullable=True)
    platform_target = Column(String(30), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="images")
    jobs = relationship("GenerationJob", back_populates="product_image")


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_image_id = Column(UUID(as_uuid=True), ForeignKey("product_images.id"), nullable=False)
    type = Column(SAEnum(JobType), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.pending, nullable=False)
    api_used = Column(String(30), nullable=True)   # anthropic | gemini | klingai | rembg
    cost_cents = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    result = Column(Text, nullable=True)           # JSON stringificado
    error_message = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    product_image = relationship("ProductImage", back_populates="jobs")


class SEODescription(Base):
    __tablename__ = "seo_descriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    platform = Column(String(30), nullable=False)  # mercadolivre | shopee | shopify
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    tags = Column(Text, nullable=True)             # JSON array stringificado
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="seo_descriptions")
