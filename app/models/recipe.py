from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Table
from sqlalchemy.dialects.postgresql import JSONB, ENUM
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.utils.id_utils import generate_id

source_type_enum = ENUM('manual', 'website', 'instagram', 'image', name='source_type_enum', create_type=True)

recipe_tags = Table(
    'recipe_tags',
    Base.metadata,
    Column('recipe_id', String, ForeignKey('recipes.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', String, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    prep_time = Column(Integer)
    cook_time = Column(Integer)
    total_time = Column(Integer)
    servings = Column(Integer)
    source_type = Column(source_type_enum, default='manual')
    source_url = Column(String)
    media = Column(JSONB)
    instructions = Column(JSONB)
    ingredients = Column(JSONB)
    notes = Column(JSONB)
    collection_id = Column(String, ForeignKey('collections.id'), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tags = relationship("Tag", secondary=recipe_tags, back_populates="recipes")
    collections = relationship("Collection", secondary="collection_recipes", back_populates="recipes")
    collection = relationship("Collection", foreign_keys=[collection_id])

class Tag(Base):
    __tablename__ = "tags"

    id = Column(String, primary_key=True, default=generate_id)
    name = Column(String, unique=True, nullable=False)
    color = Column(String)

    recipes = relationship("Recipe", secondary=recipe_tags, back_populates="tags")

