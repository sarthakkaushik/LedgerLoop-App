# Feature Plan: Family Profiles + Expense Attribution (KISS 80/20)

## Summary
Build a dedicated **Family Profiles** layer (separate from login users) so each expense can be attributed to exactly one family member profile, while preserving who logged it for audit.
This supports the primary goal: over months/years, clearly see **which family member has the highest spend**.

Chosen decisions:
- Family section uses **profiles with optional login link** (children can exist without app login).
- Expense attribution means **"this expense belongs to this family member."**
- Each expense has **one attributed member only** in v1.
- Any household user can log on behalf of any profile.
- Analytics uses **confirmed expenses only**.
- Existing expenses are backfilled to logger-matching profile.
- Default on create/edit is **current user’s linked profile**.
- Profile model includes type metadata (**adult/child/other**).

## Scope
In scope:
- Family Profiles CRUD (household-scoped).
- Optional link from profile to app user (for husband/wife).
- Add `attributed_family_member_id` to expenses.
- Update expense create/confirm/update flows to support attribution.
- Update ledger/capture UI with "Belongs To" selector.
- Add "Spend by Family Member" leaderboard view (amount-ranked).
- Backfill existing expenses.

Out of scope (explicitly deferred):
- Multi-member split per expense.
- Reimbursement/settlement accounting.
- Hard assignment permissions by role (beyond household scope).
- AI-side advanced attribution inference beyond deterministic defaulting.

## Data Model and Migration

### New table
`family_members`
- `id` (UUID, PK)
- `household_id` (UUID, indexed, required)
- `full_name` (string, required)
- `normalized_name` (string, indexed)
- `member_type` (`adult|child|other`, required)
- `linked_user_id` (UUID, nullable, unique per household when present)
- `is_active` (bool, default true)
- `created_at`, `updated_at`

Constraint strategy:
- Unique: (`household_id`, `normalized_name`, `is_active=true`) via app-level guard if partial unique not portable.
- `linked_user_id` must belong to same household (validated in service layer).

### Expense table change
Add column:
- `attributed_family_member_id` (UUID, nullable during migration, then non-null after backfill)

Foreign key:
- `expenses.attributed_family_member_id -> family_members.id`

Index:
- (`household_id`, `attributed_family_member_id`, `date_incurred`, `status`)

### Backfill strategy
- For each household, create family profiles for existing users (type `adult`, linked).
- For each existing expense, set `attributed_family_member_id` to the profile linked to `logged_by_user_id`.
- For orphaned cases, create fallback profile from logger name as `adult` unlinked.
- After backfill validation, enforce non-null in schema (or keep app-enforced non-null if DB migration safety requires staged rollout).

## Backend API and Type Changes

### New schemas
Add in `backend/app/schemas`:
- `FamilyMemberCreateRequest { full_name, member_type, linked_user_id? }`
- `FamilyMemberUpdateRequest { full_name?, member_type?, linked_user_id?, is_active? }`
- `FamilyMemberResponse { id, full_name, member_type, linked_user_id, is_active, created_at, updated_at }`
- `FamilyMemberListResponse { items: FamilyMemberResponse[] }`

### New routes
Add router `backend/app/api/family_members.py`:
- `GET /family-members`
- `POST /family-members`
- `PATCH /family-members/{id}`
- `DELETE /family-members/{id}` (soft delete, guarded if referenced by expenses)
- `POST /family-members/bootstrap` (idempotent: ensure linked adult profiles for existing users)

### Expense API changes
Update requests/responses in `backend/app/schemas/expense.py`:
- Add `attributed_family_member_id` to:
  - confirm edit payload
  - update payload
  - feed item response
  - recurring create request/response
- Keep existing `logged_by_user_id` and `logged_by_name`.

Update handlers in `backend/app/api/expenses.py`:
- On create/confirm/update:
  - validate attributed member exists, active, same household.
  - default to current user’s linked profile if missing.
- For bulk confirm:
  - per-item validation with clear warnings/errors.
- For list/dashboard:
  - include attributed member fields in feed and aggregates.

### Dashboard/analytics contract change
Extend dashboard response:
- `member_split` currently user-based should shift to family-member-based for this feature.
- Return both optional arrays for compatibility during transition:
  - `family_member_split` (new canonical)
  - `user_split` (legacy, temporary)

## Frontend Changes

### Family section
In `frontend/src/App.jsx`:
- Add dedicated Family Profiles panel or extend existing People tab.
- Show list with:
  - name
  - type badge (adult/child/other)
  - linked user (if any)
  - active/inactive state
- Actions:
  - add profile
  - edit profile
  - deactivate profile

### Expense capture and edit
- Add selector label: `Belongs To`
- Data source: `/family-members` list.
- Default selection:
  - current user linked profile when available.
  - fallback first active adult profile.
- Show in ledger rows and mobile cards:
  - `Logged by` (actor)
  - `Belongs to` (owner)

### Insights view
Add member leaderboard card/table:
- Title: `Top Spend by Family Member`
- Rank by total amount.
- Show: name, type, total amount, expense count, share %
- Period filter uses existing trend window.
- Use confirmed status data only.

## Rules and Validation
- Household boundary enforced for every family member reference.
- Inactive profiles cannot be newly assigned.
- Cannot hard-delete profile with historical expenses in v1.
- If linked user is removed from household:
  - keep profile, clear `linked_user_id`, retain history.
- If two names normalize equal, block create/update with friendly message.

## Testing Plan

### Backend tests
- Model/migration tests:
  - family member creation and uniqueness rules.
  - expense attribution FK integrity.
- API tests:
  - CRUD family members with role/household checks.
  - create/confirm/update expense with valid/invalid attribution.
  - default attribution behavior.
- Dashboard tests:
  - family-member aggregation correctness.
  - confirmed-only filter correctness.
- Backfill tests:
  - idempotent bootstrap.
  - historical expense assignment integrity.

### Frontend tests
- Unit/component:
  - Belongs To selector default and override behavior.
  - family profile CRUD form validation.
- Integration:
  - log expense under child profile and verify ledger display.
  - edit expense attribution and verify persistence.
  - leaderboard reflects updates after save.

### Manual acceptance scenarios
- Husband logs groceries for child A, wife logs school fee for child B.
- Ledger shows actor and owner distinctly.
- Insights period leaderboard ranks members by attributed spend.
- Existing historical data appears attributed to logger-derived profiles after migration.

## Rollout and Compatibility
- Phase 1: ship backend with optional `attributed_family_member_id` + bootstrap endpoint.
- Phase 2: run backfill + enable frontend selector.
- Phase 3: switch analytics UI to `family_member_split` as primary.
- Phase 4: deprecate legacy user-only split once stable.

Telemetry/logging additions:
- count of expenses created with explicit vs default attribution.
- validation failure counts for invalid profile refs.
- dashboard query latency after new joins/indexes.

## Assumptions and Defaults
- Household has exactly two primary logging adults in many cases, but model supports more.
- Children generally do not need login accounts.
- One expense belongs to one family profile in v1.
- “Most expense happening on member” means **highest total attributed amount**, not count.
- Existing UI theme/components are preserved; no visual redesign beyond required fields/views.
