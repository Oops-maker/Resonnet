<!-- Common sections for all moderator modes. Placeholders: {topic}, {ws_abs}, {expert_names_str}, {num_experts}, {num_rounds}, {summary_scope} -->

Workspace (cwd): {ws_abs}
Experts: {expert_names_str} ({num_experts} total)
Rounds: **{num_rounds}** (strict; do not exceed)

**Topic for experts**: The full topic (including any URLs) is in shared/topic.md. When invoking experts via Task, instruct them to read shared/topic.md first. If the topic contains URLs (e.g. GitHub links), experts may use WebFetch to retrieve content before discussing.

## Rules

- Each round, each expert writes to: shared/turns/round{round}_{expert}.md
- Rounds start at 1; end strictly at round {num_rounds}
- After discussion: Write shared/discussion_summary.md ({summary_scope})

## Output Language (Must Follow)

- {output_language_instruction}
