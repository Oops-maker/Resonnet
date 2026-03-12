# Image Generation Skill

Generate images via the `Wan26Media` MCP server only.

## When to Use

- Create illustrations for explanations
- Generate concept images or visual references
- Produce image assets from prompts

## Required Method (MCP Only)

- Always use MCP tools under `mcp__Wan26Media__*`.
- Do not use direct HTTP `curl` calls to DashScope in this project.
- Treat MCP as the single integration path for image generation/editing/video generation.

## Recommended MCP Workflow

1. **Select tool**  
   Choose the proper `Wan26Media` MCP tool for your task (text-to-image, image edit, text-to-video, image-to-video).
2. **Submit request**  
   Provide a clear prompt and required parameters (style, size/resolution, count, seed if needed).
3. **Handle async job**  
   If tool returns a task id, poll with the MCP status tool until `SUCCEEDED` or `FAILED`.
4. **Download immediately**  
   If a temporary external URL is returned, download it immediately.
5. **Persist to workspace**  
   Save files to `shared/generated_images/` with descriptive filenames.
6. **Return local asset URL**  
   In discussion output, only return topic asset URLs.

## Output Rule for Discussions (Must Follow)

- Never return raw DashScope OSS links directly in final discussion replies.
- After obtaining a result URL, download to `shared/generated_images/` immediately.
- In final markdown, use topic asset URLs only, e.g.:
  `![图示说明](/api/topics/<topic_id>/assets/generated_images/round2_concept_map.png)`
- If download fails repeatedly (e.g. `NoSuchBucket`, `AccessDenied`, timeout), retry MCP flow; if still failing, clearly report failure and provide text fallback.

## Retry Policy (Agent Must Retry)

To avoid one-shot failure, retry by default:

- Status polling retries: up to `60` times, every `2` seconds.
- Download retries per URL: up to `5` times.
- If URL download still fails: refresh status once (to get updated URL) and retry.
- If task is `FAILED` or repeated download failures continue: create a **new MCP task**.
- Global max attempts for one user request: `3` tasks.

Stop only when:

- image/video is downloaded and persisted successfully, or
- all retries are exhausted and a clear error is returned.

## NoSuchBucket / AccessDenied Troubleshooting

If you see `NoSuchBucket` or `AccessDenied`, check in this order:

1. Did you read the latest successful task result from MCP?
2. Is the returned URL temporary and already expired?
3. Did you download immediately after success?
4. Is your network/firewall blocking target domain access?
5. Did you accidentally return external temporary URL instead of local topic asset URL?

## Best Practices

- Keep prompts detailed: subject, style, composition, and constraints.
- Persist generated assets to local workspace immediately after successful generation.
- Avoid reusing stale external result URLs.
- Prefer deterministic settings when reproducibility matters.
