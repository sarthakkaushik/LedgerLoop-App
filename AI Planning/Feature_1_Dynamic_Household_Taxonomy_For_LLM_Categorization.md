## Feature 1: Dynamic Household Taxonomy for LLM Categorization

### Summary
Allow household admin users to manage categories and subcategories, and make expense parsing prompts dynamically use that taxonomy so new expenses are categorized against admin-defined values.

### Decisions Locked
1. Scope: per-household taxonomy.
2. Enforcement: soft enforcement at confirm time.
3. Data model: separate `category` and `subcategory` fields.

### Backend Design
1. Add taxonomy models:
- `HouseholdCategory`: `id`, `household_id`, `name`, `normalized_name`, `is_active`, `sort_order`, `created_by_user_id`, `created_at`, `updated_at`.
- `HouseholdSubcategory`: `id`, `household_category_id`, `name`, `normalized_name`, `is_active`, `sort_order`, `created_by_user_id`, `created_at`, `updated_at`.
- Add uniqueness constraints:
- `(household_id, normalized_name)` for categories.
- `(household_category_id, normalized_name)` for subcategories.

2. Extend expense model:
- Add nullable `subcategory` to `backend/app/models/expense.py` with max length 80.
- Register new models in `backend/app/models/__init__.py`.

3. Database compatibility:
- Keep `SQLModel.metadata.create_all` startup flow.
- Add compatibility helper in `backend/app/core/db.py` to ensure `expenses.subcategory` exists in deployed databases.

4. New taxonomy API (admin-managed):
- `GET /settings/taxonomy` for any authenticated household member.
- `POST /settings/taxonomy/categories` admin only.
- `PATCH /settings/taxonomy/categories/{category_id}` admin only.
- `DELETE /settings/taxonomy/categories/{category_id}` admin only (soft-delete/inactivate).
- `POST /settings/taxonomy/categories/{category_id}/subcategories` admin only.
- `PATCH /settings/taxonomy/subcategories/{subcategory_id}` admin only.
- `DELETE /settings/taxonomy/subcategories/{subcategory_id}` admin only (soft-delete/inactivate).

5. Prompt context and parser contract:
- Extend parse context to include structured taxonomy (categories with allowed subcategories).
- Update parser output contract to include `subcategory`.
- Inject taxonomy into prompt payload so provider can map expenses to valid category/subcategory pairs.

6. Soft normalization at confirmation:
- Implement in `POST /expenses/confirm`.
- Unknown category: normalize to `Other`, clear subcategory, and add warning.
- Known category + invalid/mismatched subcategory: keep category, clear subcategory, and add warning.
- Do not hard-fail confirmation for taxonomy mismatches.

7. Analytics alignment:
- Include `subcategory` in analytics CTE projection in `backend/app/api/analysis.py`.
- Update analytics prompt guidance/examples to handle subcategory questions.
- Keep null-safe handling for uncategorized/unspecified subcategories.

### Frontend Design
1. Add taxonomy client methods in `frontend/src/api.js`.
2. Add admin-only Category Manager in Household view:
- Create, rename, deactivate categories.
- Create, rename, deactivate subcategories under each category.
3. Update expense draft editor in `frontend/src/App.jsx`:
- Category dropdown sourced from household taxonomy (not static constant list).
- Subcategory dropdown dependent on selected category.
4. Non-admin users:
- Read-only view of taxonomy.

### Interfaces and Schema Changes
1. Add taxonomy schemas in `backend/app/schemas/taxonomy.py` for request/response contracts.
2. Extend expense schemas in `backend/app/schemas/expense.py`:
- Add `subcategory` to `ExpenseDraft`, `ExpenseConfirmEdit`, and `ExpenseFeedItem`.
- Add optional `warnings: list[str]` to `ExpenseConfirmResponse` for soft-normalization feedback.
3. Extend parse types in `backend/app/services/llm/types.py`:
- Add `subcategory` to `ParsedExpense`.
- Add taxonomy structure fields to `ParseContext` while retaining backward-compatible flat categories.

### Testing Plan
1. Taxonomy API tests:
- Admin can create/update/delete category and subcategory.
- Member receives `403` on taxonomy mutations.
- Household isolation is enforced.

2. Prompt/context tests:
- Parse context includes taxonomy and allowed subcategories.
- Prompt builder includes taxonomy payload and subcategory rules.

3. Expense flow tests:
- `POST /expenses/log` returns `subcategory` in parsed drafts.
- `POST /expenses/confirm` soft-normalizes invalid values and returns warnings.
- Valid category/subcategory persists correctly.

4. Analytics tests:
- Existing category analytics still works.
- Subcategory analytics queries are supported.

5. Regression tests:
- Auth/household/dashboard/feed flows remain stable with additive schema changes.

### Rollout and Safety
1. Backward compatibility:
- Existing expenses remain valid with `subcategory = null`.
- New fields are additive to API responses.

2. Default taxonomy:
- Seed new households with baseline categories including `Other`.

3. Runtime fallback:
- If taxonomy load fails during parse context construction, fall back safely to `Other` and no subcategories to keep expense logging available.

