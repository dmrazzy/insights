SUMMARY_PROMPT = (
    "You are an analyst preparing short, neutral briefs on open-source projects.  "
    "Read the README below and write a **concise, 2- to 3-sentence summary** that:\n"
    "• states the project’s core purpose / problem it solves\n"
    "• lists its main capabilities or components (1–3 key points only)\n"
    "• mentions the primary intended users or systems (e.g., smart-contract developers, node operators)\n"
    "• notes any strongly signalled context such as supported programming language, network, or runtime\n"
    "\n"
    "**Style constraints**\n"
    "• Use plain, factual language in third person (no hype, no marketing adjectives).\n"
    "• **Do not** guess or invent details that are not explicit in the README.\n"
    "• **Do not** label the project with, or copy wording from, the taxonomy below (to avoid category leakage).\n"
    "• Limit the summary to <100 words; avoid bullet lists or line breaks.\n"
    "\n"
    "Return your answer as **exactly one valid JSON object** in this form (nothing extra):\n"
    "{{\n"
    '  \"summary\": \"your summary here\"\n'
    "}}\n"
    "\n"
    "README:\n"
    "{readme_md}"
)