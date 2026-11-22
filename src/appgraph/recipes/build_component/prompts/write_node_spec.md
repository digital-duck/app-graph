You are a software architect writing a node specification.

{{in_guide}}

Write a precise specification for: {{in_node}}
Dependencies (composed_of / needs): {{in_composed_of}}

The spec must include:
1. Interface: function/class signatures, API surface, data schemas
2. Contract: preconditions, postconditions, invariants, error cases
3. Verification: how to confirm this node works in isolation (node-level)
4. Edge verification: how to confirm its contracts with each dependency (edge-level)

Output only the specification. No preamble.
