Review the current repository architecture based on the actual code, not assumptions.

Task mode: review-architecture

Review goals:
- Identify the current architecture actually used in the target area.
- Point out where the code follows or diverges from the intended selectors/services/policies/web/api structure.
- Highlight transitional compatibility constraints.
- Suggest improvements that are realistic for this repository stage.

Output format:
1. Current architecture summary
2. What is already good and should be preserved
3. Architectural problems or inconsistencies
4. Low-risk improvement plan in steps
5. Recommended next implementation task

Repository-specific focus:
- clinic_os is a transitional Django monolith.
- Legacy and refactored apps coexist intentionally.
- Template paths, JS paths, DB compatibility, and reverse URLs are important.
- Business workflows are role-sensitive and state-sensitive.
- Snapshot integrity matters in quotation/contract/document flows.
- Prefer incremental modernization over broad rewrite proposals.

Constraints:
- Do not recommend large rewrites unless absolutely necessary.
- Separate “must fix now” from “can improve later”.
- Keep advice grounded in the current codebase reality.

If the user asks for follow-up code after the review, switch to implementation-ready output.