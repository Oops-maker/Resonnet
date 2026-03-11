# Web Search Skill

Use real-time internet search to enhance discussion accuracy and timeliness.

## When to Use

- Need latest information (news, events, data)
- Verify facts or claims
- Find specific information not in training data
- Cross-reference multiple sources

## How to Use

Call the web search API with a specific query:

```bash
curl --location 'https://api.bocha.cn/v1/web-search' \
  --header 'Authorization: Bearer ${BOCHA_API_KEY}' \
  --header 'Content-Type: application/json' \
  --data '{
    "query": "Search query here",
    "summary": true,
    "freshness": "noLimit",
    "count": 10
  }'
```

## Best Practices

- **Be specific**: Use precise keywords and time ranges
- **Multiple queries**: Try different phrasings for comprehensive results
- **Verify sources**: Check credibility of search results
- **Cite properly**: Reference sources when using information

## Example Queries

- "Latest AI research 2026"
- "Climate change impact statistics 2025-2026"
- "Quantum computing breakthroughs recent news"
