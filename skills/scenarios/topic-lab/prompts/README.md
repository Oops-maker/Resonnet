# Topic Lab Prompts

AI prompts that drive **feature behavior**: expert/moderator generation, round discussion, @mention reply.

## Difference from experts/ and moderator/

- **experts/** = *what* roles exist (content: physicist, biologist, etc.)
- **moderator/** = *what* discussion modes exist (content: standard, brainstorm, etc.)
- **prompts/** = *how* the AI behaves in each feature (functional: generation style, reply constraints, etc.)

## File Layout

| File | Function | Trigger |
|------|----------|---------|
| `expert_generation.md` | System prompt for AI expert generation (role-only output) | User clicks "AI generate" when creating expert |
| `expert_user_message.md` | User message template | Same |
| `moderator_generation.md` | System prompt for AI moderator generation (role-only output) | User clicks "AI generate" in moderator dialog |
| `moderator_user_message.md` | User message template | Same |
| `moderator_system.md` | Moderator system prompt for round discussion | POST .../discussion |
| `expert_reply_skill.md` | Skill for @mention expert reply | POST .../posts/mention |
| `expert_reply_user_message.md` | User message template | Same |

## Adding or Overriding

To customize a feature: edit the corresponding file. To add a new scenario with different prompts: copy this `prompts/` dir, then modify. Missing files fall back to `app/prompts/`.
