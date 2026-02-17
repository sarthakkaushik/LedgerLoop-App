from pydantic import BaseModel, Field


class TaxonomySubcategoryItem(BaseModel):
    id: str
    name: str
    is_active: bool
    sort_order: int


class TaxonomyCategoryItem(BaseModel):
    id: str
    name: str
    is_active: bool
    sort_order: int
    subcategories: list[TaxonomySubcategoryItem]


class TaxonomyListResponse(BaseModel):
    categories: list[TaxonomyCategoryItem]


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sort_order: int | None = None


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    sort_order: int | None = None
    is_active: bool | None = None


class SubcategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sort_order: int | None = None


class SubcategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    sort_order: int | None = None
    is_active: bool | None = None
