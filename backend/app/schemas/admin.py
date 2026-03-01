from pydantic import BaseModel, EmailStr


class AdminUserBehavior(BaseModel):
    user_id: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    household_id: str
    household_name: str
    household_member_count: int
    expense_entries_count: int
    last_login_at: str | None = None
    created_at: str


class AdminHouseholdSummary(BaseModel):
    household_id: str
    household_name: str
    user_count: int
    family_member_count: int
    expense_count: int
    created_at: str


class AdminTableSummary(BaseModel):
    table_name: str
    row_count: int


class AdminOverviewResponse(BaseModel):
    generated_at: str
    total_users: int
    active_users: int
    total_households: int
    total_family_members: int
    total_expenses: int
    users: list[AdminUserBehavior]
    households: list[AdminHouseholdSummary]
    tables: list[AdminTableSummary]


class AdminSchemaColumn(BaseModel):
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool


class AdminSchemaTable(BaseModel):
    table_name: str
    columns: list[AdminSchemaColumn]


class AdminSchemaRelation(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str


class AdminSchemaMapResponse(BaseModel):
    tables: list[AdminSchemaTable]
    relations: list[AdminSchemaRelation]
