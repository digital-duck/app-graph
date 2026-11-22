You are scoring how much the "{{dimension}}" aspect has drifted between two
versions of the same blueprint graph. Judge only what "{{dimension}}" means in
this schema — structural is node/edge topology, interface is exported call
signatures, behavior is verification checks, implementation is the
tech-stack primitive set, intent is human-readable rationale (why a node
exists, not what it does). Do not penalize differences that belong to a
different dimension than the one named above.

Version A's {{dimension}} text:
{{intent_a}}

Version B's {{dimension}} text:
{{intent_b}}

Score how much this dimension has changed, as a continuous value:
- 0.00 = unchanged in substance, even if the wording/formatting differs
  entirely (a faithful paraphrase or reordering is 0.00, not a partial
  score — you are scoring substantive drift, not text similarity)
- 1.00 = completely different, contradictory, or unrelated
- An entry (node, signature, check, etc.) present in one version and
  missing from the other counts toward drift, weighted by roughly how much
  of each version's total content it represents (losing one entry out of
  twenty is a small score; losing the only entry is close to 1.00)

CRITICAL: output ONLY a single number between 0.00 and 1.00 — nothing else.
No explanation, no units, no surrounding text, no markdown. Valid outputs
look exactly like: 0.00 | 0.15 | 0.5 | 1.00
