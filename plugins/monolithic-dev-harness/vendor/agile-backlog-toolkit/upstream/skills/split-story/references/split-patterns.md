# Split Pattern Catalog

Reference for the `split-story` skill ANALYZE phase. Each pattern includes: detection signals
(what to look for in the story body and ACs), a decision rule for auto-selection, and a
negative example so the agent knows when NOT to pick it.

## Pattern 1 — Workflow Step

**What it means:** The story describes a sequential process with multiple distinct steps. Each
step can be delivered independently and yields value on its own.

**Detection signals:**
- Body or ACs contain sequential connectives: "first", "then", "after", "next", "finally",
  "when X is done, Y"
- Numbered list of actions in expected behavior or ACs
- The story title contains "flow", "process", or "wizard"
- Body references multiple screens or pages in a navigation sequence

**Split rule:** One sub-story per sequential step. Sub-story N can be built and tested before
step N+1 exists.

**Coverage rule:** Each step maps to one AC cluster. No step is left without a sub-story.

**Counter-signal (don't pick this pattern if):** Steps are not independently deployable — e.g.,
step 2 is only testable if step 1 is in prod. Use Happy/Unhappy Path instead if the relationship
is success vs. error.

**Example:**
Original: "As a user, I can register, verify my email, and set my profile."
Split: (1) Register — account creation, (2) Email verification, (3) Profile setup.

---

## Pattern 2 — Business Rule

**What it means:** The story applies different logic depending on a condition. Each distinct
rule/branch can be built and tested independently.

**Detection signals:**
- ACs contain "if / when / unless / except when" branching
- ACs list multiple independent conditions each with different outcomes
- Body mentions user roles, plan tiers, permission levels, or regional rules
- Multiple `[ ]` AC checkboxes each govern a different scenario

**Split rule:** One sub-story per distinct rule branch. Sub-story titles include the condition:
"…when user is admin", "…for Pro-tier accounts".

**Coverage rule:** Every condition in the original ACs appears in exactly one sub-story.

**Counter-signal:** If branches share so much code that delivering one without the other is
meaningless (e.g., toggle on/off), use Happy/Unhappy Path instead.

**Example:**
Original: "Price shown in cart changes based on whether user has a coupon, is logged in, or
qualifies for bulk discount."
Split: (1) Logged-out base price, (2) Coupon application, (3) Bulk discount rule.

---

## Pattern 3 — Happy / Unhappy Path

**What it means:** The story describes both a success flow and one or more error/edge cases.
The error flows are independent enough to be validated separately.

**Detection signals:**
- ACs include both positive outcomes and error/validation scenarios
- Body uses phrases like "if invalid", "on failure", "error message", "fallback", "retry"
- ACs mix `should succeed when` and `should show error when` items
- The story handles a form or API call with both valid and invalid inputs

**Split rule:** Sub-story 1 = happy path only. Sub-story 2+ = error / edge cases grouped by
similarity. Sub-story 2 can reference Sub-story 1's success state as a prerequisite for negative
testing.

**Coverage rule:** Every AC item maps to happy or unhappy; none is orphaned.

**Counter-signal:** If the error handling is a single validation (one input, one error message),
it is not big enough to warrant a separate sub-story. Absorb into the happy-path story.

**Example:**
Original: "User submits payment form; card is charged; if card is declined, show error."
Split: (1) Successful payment flow, (2) Declined card and retry handling.

---

## Pattern 4 — CRUD Operation

**What it means:** The story covers multiple create / read / update / delete operations on the
same entity. Each operation is independently shippable.

**Detection signals:**
- ACs contain "create", "list", "view", "edit", "update", "delete", "archive" for the same noun
- Body or title references a management screen or admin panel
- Story points are high because the entity has multiple lifecycle operations

**Split rule:** One sub-story per CRUD verb. Sequence: Create → Read/List → Update → Delete
(so each sub-story can be validated end-to-end on the prior one's output). Read and List may
be combined if trivially similar.

**Coverage rule:** Every operation mentioned in original ACs appears in exactly one sub-story.

**Counter-signal:** If the story only has two operations (e.g., create + delete with no
list/edit), verify each sub-story still exceeds the ceiling before splitting — a two-operation
story may already be right-sized.

**Example:**
Original: "Admin can create, view, edit, and delete user accounts."
Split: (1) Create account, (2) View/list accounts, (3) Edit account, (4) Delete account.

---

## Pattern 5 — Data Variation

**What it means:** The story handles the same operation for multiple distinct data types, entity
subtypes, or input formats. Each variation has different validation, rendering, or processing
logic.

**Detection signals:**
- ACs list the same verb applied to multiple nouns: "upload PDF", "upload image", "upload CSV"
- Body mentions multiple entity subtypes: "internal user", "external contractor", "guest"
- Story handles different API payload schemas or response shapes
- Complexity is driven by the Dados driver (modeling or migration across variants)

**Split rule:** One sub-story per data variant. All sub-stories share the same operation; they
differ in the data contract and validation rules.

**Coverage rule:** Every data type / variant mentioned in original ACs appears in exactly one
sub-story.

**Counter-signal:** If the variants differ only in a label or color (purely presentational),
they are not separate sub-stories — they are configuration. Do not split.

**Example:**
Original: "System accepts file uploads: PDF documents, PNG/JPEG images, and CSV data exports."
Split: (1) PDF upload and validation, (2) Image upload and validation, (3) CSV upload and
parsing.

---

## Auto-Selection Decision Tree

Evaluate signals in this order. Use the first pattern whose primary signal is present. If two
patterns tie, prefer the one with more distinct AC items mapping to it.

```text
1. Body/ACs describe a sequential process with independently deliverable steps?
   → Workflow Step

2. ACs contain distinct condition branches (if/when/unless) each with different outcomes?
   → Business Rule

3. ACs mix success scenarios and error/edge-case scenarios?
   → Happy / Unhappy Path

4. Story covers multiple CRUD verbs on the same entity?
   → CRUD Operation

5. Story handles the same operation across multiple data types or entity variants?
   → Data Variation
```

If no pattern clearly fits, surface this to the user before drafting and ask them to identify
the natural split axis.
