# Feature 3: Global Command Bar Quick Add From Any Tab

Date: 2026-02-17
Owner: Product + Frontend
Status: Proposed

## Objective

Enable users to log expenses from anywhere in the app without switching tabs, using a global command bar that supports natural-language input and fast confirmation.

## Problem Statement

Current logging is tied to specific screens, which adds navigation friction and slows capture velocity. Users should be able to quickly add an expense from any context (Insights, People & Access, Settings, Ledger, Capture).

## Success Criteria

1. Quick add is available from all authenticated app views.
2. User can open, parse, review, and save an expense without leaving current tab.
3. Clarification-required cases are routed to review flow with no data loss.
4. Keyboard-first and mobile-friendly interaction both work.

## Scope

### In Scope

1. Global command bar modal accessible app-wide.
2. Open triggers:
   - `Ctrl + K` / `Cmd + K`
   - Header button: `Quick Add`
   - Mobile FAB: `+`
3. Natural language parse using existing expense parsing endpoint.
4. Inline draft editing (amount, currency, category, subcategory, date, description, merchant/item, recurring).
5. Direct save flow using existing confirm endpoint.
6. Clarification flow that pushes unresolved entries to Capture review queue.
7. Toast/inline feedback and telemetry events.

### Out of Scope

1. New backend parser logic.
2. Voice input.
3. Offline mode.

## UX Flow

### Primary Flow (High Confidence)

1. User opens command bar.
2. Enters text: `Paid 1200 for electricity yesterday`.
3. UI shows parsing state.
4. Parsed draft appears in modal editor.
5. User clicks `Save to Ledger`.
6. Success toast appears; modal closes; user remains on current tab.

### Clarification Flow

1. Parser returns clarification needed.
2. UI shows `Need one more detail` with questions.
3. User can:
   - answer in modal and re-run parse, or
   - `Send to Review Queue`.
4. Draft is preserved and visible in `Capture > Review Queue`.

### Failure Flow

1. API/network error is shown inline.
2. User can retry parse/save.
3. No silent failures.

## Information Architecture Placement

1. Command bar is app-shell level, not tab-level.
2. Trigger and modal are globally mounted for authenticated users.
3. Capture remains the deep editing surface; command bar is the fast-entry surface.

## Technical Approach

## Frontend Components

1. `GlobalQuickAddLauncher`
   - header button + mobile FAB.
2. `GlobalQuickAddModal`
   - input, status, editable draft, actions.
3. `GlobalQuickAddProvider` (or app-shell state)
   - open/close control + keyboard shortcut binding.

## API Usage (Reuse Existing)

1. Parse: existing `parseExpenseText(token, text)`.
2. Confirm: existing `confirmExpenses(token, payload)`.
3. Optional taxonomy preload: existing `fetchTaxonomy(token)` for category/subcategory dropdowns.

No new backend endpoints required for Phase 1.

## Data and State Rules

1. Modal keeps local transient draft state.
2. Parse result replaces prior transient state only after success.
3. Save action requires at least one confirmable draft item.
4. Close modal behavior:
   - if unsaved changes exist, show discard confirmation modal.

## Accessibility Requirements

1. Full keyboard operation:
   - open/close, tab order, submit.
2. Focus trap while modal is open.
3. Return focus to invoker on close.
4. `aria-label` for modal and key buttons.
5. Respect `prefers-reduced-motion`.

## Observability and Analytics

Track these events with timestamp + user_id + household_id + source:

1. `quick_add_opened` (source: shortcut/header/fab)
2. `quick_add_submitted`
3. `quick_add_parse_success`
4. `quick_add_parse_clarification_required`
5. `quick_add_saved_to_ledger`
6. `quick_add_sent_to_review_queue`
7. `quick_add_closed_without_action`
8. `quick_add_error`

## Performance and UX Targets

1. Modal open interaction: < 100 ms perceived delay.
2. Parse loading state visible immediately (< 150 ms).
3. No full-page re-render required for command bar actions.

## Rollout Plan

### Phase 1

1. Implement command bar with parse + confirm.
2. Ship behind feature flag `global_quick_add`.
3. Enable for internal users/admin first.

### Phase 2

1. Enable for all authenticated users.
2. Add `Send to Review Queue` routing and confirmation polish.
3. Monitor conversion and error metrics.

## QA and Test Plan

## Functional Tests

1. Open command bar from each tab.
2. Keyboard shortcut works and does not trigger inside focused text inputs where blocked.
3. Parse success -> save success -> ledger reflects new expense.
4. Clarification path routes to review queue.
5. Retry path after API failure.

## UX Tests

1. Modal focus trapping and escape behavior.
2. Mobile FAB visibility and usability.
3. Unsaved changes warning on close.

## Permission Tests

1. Admin and member can quick-add.
2. Unauthenticated user cannot access command bar.

## Definition of Done

1. Command bar available app-wide for authenticated users.
2. End-to-end parse and save works with existing APIs.
3. Clarification path is non-destructive and actionable.
4. Accessibility baseline for modal interactions is met.
5. Telemetry events are emitted and verifiable.
