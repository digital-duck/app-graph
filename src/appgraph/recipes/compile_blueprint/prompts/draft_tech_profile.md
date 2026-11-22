None of this project's existing tech_profiles (spl/tech_profiles.py's
PROFILES dict: python_fastapi, vue_typescript, python_library, curriculum)
fit the application below — you proposed a new profile name: {{in_profile_name}}.

Static analysis:
{{in_analysis_json}}

Representative source file contents:
{{in_source_context}}

Draft a new tech_profile writeup for **{{in_profile_name}}**, in the same shape
as an existing PROFILES entry: a style-guide prompt fragment that would be
prepended to every node-generation call for an app of this shape (language/
framework conventions, file layout, naming rules, what NOT to invent —
e.g. this project's existing profiles all include a "never use a graph node
id as a generated identifier" rule; keep that rule and add whatever else is
specific to this stack), plus a suggested verify command (the equivalent of
VERIFY_CMDS — e.g. `pytest` for Python, `streamlit run --headless` health
check, `npm test`, or an HTML validator, whichever fits what you saw).

This is a REVIEWABLE DRAFT, not something that gets merged automatically —
spl/tech_profiles.py's PROFILES/VERIFY_CMDS dicts are a shared, repo-wide
style guide governing every future app of this shape, so a human reviews
and merges this by hand. Write it as a short Markdown document:

# Proposed tech_profile: {{in_profile_name}}

## Style guide (PROFILES["{{in_profile_name}}"] candidate text)
<the prompt-fragment prose itself>

## Suggested verify command (VERIFY_CMDS["{{in_profile_name}}"] candidate)
<the command>

## Why no existing profile fit
<one or two sentences>

Output ONLY that Markdown document, no other commentary.
