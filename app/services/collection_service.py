from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from typing import List, Optional
from app.models.collection import Collection
from app.models.recipe import Recipe
from app.schemas.collection import CollectionCreate, CollectionUpdate, CollectionWithStats
from fastapi import HTTPException, status

class CollectionService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_collections(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Collection]:
        """Get all collections for a user with pagination."""
        return (
            self.db.query(Collection)
            .filter(Collection.user_id == user_id)
            .order_by(Collection.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_user_collections_with_stats(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[CollectionWithStats]:
        """Get all collections for a user with recipe counts."""
        # Get collections first
        collections = (
            self.db.query(Collection)
            .filter(Collection.user_id == user_id)
            .order_by(Collection.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        # Calculate recipe counts for each collection
        result = []
        for collection in collections:
            # Count recipes that have this collection_id (direct relationship)
            recipe_count = (
                self.db.query(Recipe)
                .filter(Recipe.collection_id == collection.id)
                .count()
            )
            
            collection_dict = {
                "id": collection.id,
                "user_id": collection.user_id,
                "name": collection.name,
                "description": collection.description,
                "created_at": collection.created_at,
                "updated_at": collection.updated_at,
                "recipe_count": recipe_count
            }
            result.append(CollectionWithStats(**collection_dict))
        
        return result

    def get_collection_by_id(
        self, 
        collection_id: str, 
        user_id: str, 
        include_recipes: bool = False
    ) -> Optional[Collection]:
        """Get a specific collection by ID for a user."""
        query = self.db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == user_id
        )
        
        if include_recipes:
            query = query.options(selectinload(Collection.recipes))
        
        return query.first()

    def create_collection(
        self, 
        collection_data: CollectionCreate, 
        user_id: str
    ) -> Collection:
        """Create a new collection for a user."""
        # Check if collection name already exists for this user
        existing = (
            self.db.query(Collection)
            .filter(
                Collection.user_id == user_id,
                Collection.name == collection_data.name
            )
            .first()
        )
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Collection with name '{collection_data.name}' already exists"
            )
        
        # Create new collection
        db_collection = Collection(
            user_id=user_id,
            name=collection_data.name,
            description=collection_data.description
        )
        
        self.db.add(db_collection)
        self.db.commit()
        self.db.refresh(db_collection)
        
        return db_collection

    def update_collection(
        self, 
        collection_id: str, 
        collection_data: CollectionUpdate, 
        user_id: str
    ) -> Optional[Collection]:
        """Update an existing collection."""
        db_collection = self.get_collection_by_id(collection_id, user_id)
        
        if not db_collection:
            return None
        
        # Check if new name conflicts with existing collections (if name is being changed)
        if (collection_data.name and 
            collection_data.name != db_collection.name):
            existing = (
                self.db.query(Collection)
                .filter(
                    Collection.user_id == user_id,
                    Collection.name == collection_data.name,
                    Collection.id != collection_id
                )
                .first()
            )
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Collection with name '{collection_data.name}' already exists"
                )
        
        # Update fields that were provided
        update_data = collection_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_collection, field, value)
        
        self.db.commit()
        self.db.refresh(db_collection)
        
        return db_collection

    def delete_collection(self, collection_id: str, user_id: str) -> bool:
        """Delete a collection by ID."""
        db_collection = self.get_collection_by_id(collection_id, user_id)
        
        if not db_collection:
            return False
        
        self.db.delete(db_collection)
        self.db.commit()
        
        return True

    def add_recipe_to_collection(
        self, 
        collection_id: str, 
        recipe_id: str, 
        user_id: str
    ) -> bool:
        """Add a recipe to a collection."""
        # Verify collection belongs to user
        collection = self.get_collection_by_id(collection_id, user_id)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found"
            )
        
        # Verify recipe belongs to user
        recipe = (
            self.db.query(Recipe)
            .filter(Recipe.id == recipe_id, Recipe.user_id == user_id)
            .first()
        )
        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipe not found"
            )
        
        # Add recipe to collection if not already there
        if recipe not in collection.recipes:
            collection.recipes.append(recipe)
            self.db.commit()
        
        return True

    def remove_recipe_from_collection(
        self, 
        collection_id: str, 
        recipe_id: str, 
        user_id: str
    ) -> bool:
        """Remove a recipe from a collection."""
        # Verify collection belongs to user
        collection = self.get_collection_by_id(collection_id, user_id, include_recipes=True)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found"
            )
        
        # Find and remove recipe from collection
        recipe_to_remove = None
        for recipe in collection.recipes:
            if recipe.id == recipe_id:
                recipe_to_remove = recipe
                break
        
        if recipe_to_remove:
            collection.recipes.remove(recipe_to_remove)
            self.db.commit()
            return True
        
        return False

    def count_user_collections(self, user_id: str) -> int:
        """Count total collections for a user."""
        return (
            self.db.query(Collection)
            .filter(Collection.user_id == user_id)
            .count()
        )