# Feature 2: Frontend UX Information Architecture and User Flow Revamp

Date: 2026-02-17
Owner: Product + Frontend
Status: Proposed

## Objective

Upgrade the current frontend from a feature-centric/old-school flow to a modern, job-based product experience with:

- clear navigation by user intent,
- better async/loading feedback,
- consistent naming and tone,
- cleaner separation of collaboration vs settings responsibilities.

## Current-State Issues (Validated)

1. Category administration is placed inside Household collaboration UI.
2. Taxonomy APIs are settings-domain endpoints, but UI places them in a collaboration-domain panel.
3. Two parallel AI surfaces (`Chat Log` and `Analytics Chat`) split user intent and create navigation friction.
4. Loading feedback is mostly text swaps instead of modern perceived-performance patterns.
5. Destructive actions rely on browser-native confirms.
6. Product naming and tone are inconsistent across screens.

## Final Information Architecture

Main navigation should be:

1. Capture
2. Ledger
3. Insights
4. People & Access
5. Settings

### Mapping from current tabs

- Chat Log -> Capture
- Dashboard -> Insights (Overview)
- Analytics Chat -> Insights (Ask AI)
- Household -> People & Access
- Category Manager (currently in Household) -> Settings > Categories & Subcategories

## Category Manager Placement Decision (Final)

Category Manager is not correctly placed in Household.

It should move to `Settings` because it is:

- an admin configuration function,
- cross-cutting taxonomy control,
- not a collaboration/member-access workflow.

Household should only include:

- invite flow,
- member roles and access control,
- who logged what,
- shared ledger visibility.

## Final End-to-End User Flows

### 1) First-time Admin Onboarding

1. Register
2. Quick onboarding (2-3 guided steps)
3. Land in Capture
4. Submit first expense input
5. Review AI draft
6. Save to Ledger
7. Optional CTA to Insights

### 2) Household Member Onboarding

1. Join with invite code
2. Land in People & Access summary (role + context)
3. Continue to Capture

### 3) Daily Capture Flow

1. Open Capture
2. Enter natural language expense
3. See typing/loading state
4. Review editable draft card(s)
5. Save to Ledger
6. See clear success confirmation + next action

### 4) Insights / Ask AI Flow

1. Open Insights
2. Ask question or choose prompt chip
3. Receive answer + chart/table cards
4. Ask follow-up in same conversational thread

### 5) People & Access Flow

1. Open People & Access
2. Generate/refresh invite
3. Manage members/roles
4. Review shared ledger actions

### 6) Taxonomy Settings Flow

1. Open Settings > Categories & Subcategories
2. Add/rename/deactivate category/subcategory
3. Show impact warnings before destructive changes

## UX and Copy Interventions

### Navigation and Structure

1. Convert to job-based IA.
2. Consolidate analytics conversation under Insights.
3. Keep taxonomy completely outside Household.

### Loading and Feedback

1. Add auth transition loading screen.
2. Add skeleton loaders for dashboard and list panels.
3. Add typing indicator for AI responses.
4. Keep row-level busy states for action buttons.

### Confirmation and Safety

1. Replace `window.confirm` with in-app confirmation modal.
2. Use consistent toast/inline feedback on success/error.

### Naming/Tone Updates

1. Category Manager -> Categories & Subcategories
2. Confirm Expenses -> Save to Ledger
3. Needs clarification -> Need one more detail
4. Household Collaboration -> People & Access

## Implementation Plan (Recommended)

### Phase 1 (Immediate UX fixes)

1. Move taxonomy UI/state/handlers to new `SettingsPanel`.
2. Update tab labels and routing.
3. Replace browser confirms with modal component.
4. Improve loading states (chat + panel + auth transition).

### Phase 2 (Flow consolidation)

1. Merge `Chat Log` and `Analytics Chat` journey into a single coherent AI experience (within Capture/Insights boundaries).
2. Add conversation continuity and follow-up context.
3. Add first-session guided prompts.

### Phase 3 (Quality/polish)

1. Refine empty states and onboarding hints.
2. Add role-aware controls and guardrails in Settings.
3. Standardize microcopy and information hierarchy.

## Success Metrics

1. Time to first confirmed expense < 60 seconds.
2. Parse-to-confirm conversion > 70%.
3. Weekly active households with at least one AI query.
4. Reduction in navigation switching between analysis and capture surfaces.

## Sign-Off Checklist

- Category tools are no longer in Household.
- Household is strictly collaboration/access.
- Settings holds all taxonomy admin operations.
- Async interactions use modern loading patterns.
- Destructive actions use in-app modal confirms.
- Primary UI copy is non-technical and user-outcome focused.
