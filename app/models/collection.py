from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Table, func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.utils.id_utils import generate_id

# Many-to-many association table for recipes and collections
collection_recipes = Table(
    'collection_recipes',
    Base.metadata,
    Column('collection_id', String, ForeignKey('collections.id', ondelete='CASCADE'), primary_key=True),
    Column('recipe_id', String, ForeignKey('recipes.id', ondelete='CASCADE'), primary_key=True)
)

class Collection(Base):
    __tablename__ = "collections"
    
    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to user
    user = relationship("User", back_populates="collections")
    
    # Many-to-many relationship with recipes
    recipes = relationship("Recipe", secondary=collection_recipes, back_populates="collections")
    
    def __repr__(self):
        return f"<Collection(id={self.id}, name={self.name}, user_id={self.user_id})>"