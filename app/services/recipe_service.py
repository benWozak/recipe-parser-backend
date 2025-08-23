from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, or_
from typing import List, Optional
from app.models.recipe import Recipe, Tag
from app.models.collection import Collection
from app.schemas.recipe import RecipeCreate, RecipeUpdate

class RecipeService:
    def __init__(self, db: Session):
        self.db = db

    def _populate_recipe_collection_info(self, recipe: Recipe):
        """Helper method to populate collection_id and collection info for recipe responses"""
        # If recipe has a direct collection_id, use that (primary approach)
        if recipe.collection_id:
            # Ensure the collection relationship is loaded if needed
            if not recipe.collection:
                recipe.collection = self.db.query(Collection).filter(Collection.id == recipe.collection_id).first()
        # Fallback: check many-to-many collections for backwards compatibility
        elif recipe.collections:
            recipe.collection_id = recipe.collections[0].id
            recipe.collection = recipe.collections[0]
        else:
            recipe.collection_id = None
            recipe.collection = None
        return recipe

    def get_user_recipes(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        collection_id: Optional[str] = None
    ) -> List[Recipe]:
        query = self.db.query(Recipe).filter(Recipe.user_id == user_id)
        
        # Eagerly load collections and other relationships
        query = query.options(
            selectinload(Recipe.collections),
            selectinload(Recipe.collection),
            selectinload(Recipe.tags)
        )
        
        if search:
            query = query.filter(
                or_(
                    Recipe.title.ilike(f"%{search}%"),
                    Recipe.description.ilike(f"%{search}%")
                )
            )
        
        if tags:
            query = query.join(Recipe.tags).filter(Tag.name.in_(tags))
        
        if collection_id:
            if collection_id == 'uncollected':
                # Show recipes that are not in any collection (both direct and many-to-many)
                query = query.filter(
                    and_(
                        Recipe.collection_id.is_(None),
                        ~Recipe.collections.any()
                    )
                )
            else:
                # Show recipes that are in the specified collection (check both direct and many-to-many)
                query = query.filter(
                    or_(
                        Recipe.collection_id == collection_id,
                        Recipe.collections.any(Collection.id == collection_id)
                    )
                )
        
        recipes = query.offset(skip).limit(limit).all()
        return [self._populate_recipe_collection_info(recipe) for recipe in recipes]

    def get_recipe(self, recipe_id: str, user_id: str) -> Optional[Recipe]:
        recipe = self.db.query(Recipe).options(
            selectinload(Recipe.collections),
            selectinload(Recipe.collection),
            selectinload(Recipe.tags)
        ).filter(
            and_(Recipe.id == recipe_id, Recipe.user_id == user_id)
        ).first()
        
        if recipe:
            return self._populate_recipe_collection_info(recipe)
        return None

    def create_recipe(self, recipe_data: RecipeCreate, user_id: str) -> Recipe:
        recipe_dict = recipe_data.dict(exclude={'tags', 'collection_id'})
        recipe = Recipe(**recipe_dict, user_id=user_id)
        
        # Handle collection assignment with direct collection_id
        if recipe_data.collection_id:
            collection = self.db.query(Collection).filter(
                and_(Collection.id == recipe_data.collection_id, Collection.user_id == user_id)
            ).first()
            if collection:
                recipe.collection_id = recipe_data.collection_id
        
        self.db.add(recipe)
        self.db.flush()

        for tag_data in recipe_data.tags:
            tag_name = tag_data.name if hasattr(tag_data, 'name') else str(tag_data)
            tag_color = tag_data.color if hasattr(tag_data, 'color') else None
            
            tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, color=tag_color)
                self.db.add(tag)
                self.db.flush()
            elif tag_color and not tag.color:
                # Update color if tag exists but doesn't have a color
                tag.color = tag_color
            recipe.tags.append(tag)

        self.db.commit()
        self.db.refresh(recipe)
        return self._populate_recipe_collection_info(recipe)

    def update_recipe(
        self, 
        recipe_id: str, 
        recipe_update: RecipeUpdate, 
        user_id: str
    ) -> Optional[Recipe]:
        recipe = self.get_recipe(recipe_id, user_id)
        if not recipe:
            return None

        update_data = recipe_update.dict(exclude_unset=True, exclude={'tags', 'collection_id'})
        for field, value in update_data.items():
            setattr(recipe, field, value)

        if recipe_update.tags is not None:
            recipe.tags.clear()
            for tag_data in recipe_update.tags:
                tag_name = tag_data.name if hasattr(tag_data, 'name') else str(tag_data)
                tag_color = tag_data.color if hasattr(tag_data, 'color') else None
                
                tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name, color=tag_color)
                    self.db.add(tag)
                    self.db.flush()
                elif tag_color and not tag.color:
                    # Update color if tag exists but doesn't have a color
                    tag.color = tag_color
                recipe.tags.append(tag)

        # Handle collection assignment
        if 'collection_id' in recipe_update.dict(exclude_unset=True):
            if recipe_update.collection_id:
                # Verify the collection exists and belongs to the user
                collection = self.db.query(Collection).filter(
                    and_(Collection.id == recipe_update.collection_id, Collection.user_id == user_id)
                ).first()
                if collection:
                    recipe.collection_id = recipe_update.collection_id
                    # Also clear any many-to-many relationships for consistency
                    recipe.collections.clear()
                else:
                    # Invalid collection_id, clear it
                    recipe.collection_id = None
            else:
                # collection_id is None, clear the assignment
                recipe.collection_id = None
                recipe.collections.clear()

        self.db.commit()
        self.db.refresh(recipe)
        return self._populate_recipe_collection_info(recipe)

    def delete_recipe(self, recipe_id: str, user_id: str) -> bool:
        recipe = self.get_recipe(recipe_id, user_id)
        if not recipe:
            return False
        
        self.db.delete(recipe)
        self.db.commit()
        return True