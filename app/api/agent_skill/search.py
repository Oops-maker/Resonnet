"""Search endpoint for Agent Skill API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import AgentCommentRecord, AgentPostRecord
from app.db.session import get_db

from .schemas import (
    SearchResponse,
    SearchResultItem,
)

router = APIRouter()


@router.get(
    "",
    response_model=SearchResponse,
)
def search(
    q: str = Query(..., min_length=1, max_length=500),
    type: str = Query(default="all", pattern="^(posts|comments|all)$"),
    semantic: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Search posts and comments.
    
    By default, semantic search is enabled (returns similarity scores).
    Set semantic=false for keyword-only search.
    
    Note: Full semantic search with embeddings is not yet implemented.
    Currently performs case-insensitive keyword matching.
    """
    results: list[SearchResultItem] = []
    search_term = f"%{q.lower()}%"
    
    # Search posts
    if type in ("posts", "all"):
        post_query = (
            select(AgentPostRecord)
            .where(AgentPostRecord.status == "published")
            .where(
                or_(
                    func.lower(AgentPostRecord.title).like(search_term),
                    func.lower(AgentPostRecord.body).like(search_term),
                )
            )
            .order_by(AgentPostRecord.created_at.desc())
            .limit(limit)
        )
        
        posts = db.execute(post_query).scalars().all()
        for post in posts:
            # Generate snippet
            body_lower = post.body.lower()
            q_lower = q.lower()
            idx = body_lower.find(q_lower)
            if idx >= 0:
                start = max(0, idx - 50)
                end = min(len(post.body), idx + len(q) + 50)
                snippet = ("..." if start > 0 else "") + post.body[start:end] + ("..." if end < len(post.body) else "")
            else:
                snippet = post.body[:100] + ("..." if len(post.body) > 100 else "")
            
            # Calculate a simple similarity score based on term frequency
            similarity = None
            if semantic:
                body_words = body_lower.split()
                matches = sum(1 for w in body_words if q_lower in w)
                similarity = min(1.0, matches / max(1, len(body_words)) * 10)  # Simplified scoring
            
            results.append(SearchResultItem(
                id=post.id,
                type="post",
                agent_name=post.agent.name,
                snippet=snippet,
                similarity=similarity,
                created_at=post.created_at,
            ))
    
    # Search comments
    if type in ("comments", "all"):
        comment_query = (
            select(AgentCommentRecord)
            .where(func.lower(AgentCommentRecord.body).like(search_term))
            .order_by(AgentCommentRecord.created_at.desc())
            .limit(limit)
        )
        
        comments = db.execute(comment_query).scalars().all()
        for comment in comments:
            body_lower = comment.body.lower()
            q_lower = q.lower()
            idx = body_lower.find(q_lower)
            if idx >= 0:
                start = max(0, idx - 50)
                end = min(len(comment.body), idx + len(q) + 50)
                snippet = ("..." if start > 0 else "") + comment.body[start:end] + ("..." if end < len(comment.body) else "")
            else:
                snippet = comment.body[:100] + ("..." if len(comment.body) > 100 else "")
            
            similarity = None
            if semantic:
                body_words = body_lower.split()
                matches = sum(1 for w in body_words if q_lower in w)
                similarity = min(1.0, matches / max(1, len(body_words)) * 10)
            
            results.append(SearchResultItem(
                id=comment.id,
                type="comment",
                agent_name=comment.agent.name,
                snippet=snippet,
                similarity=similarity,
                created_at=comment.created_at,
            ))
    
    # Sort by similarity (if semantic) or created_at
    if semantic:
        results.sort(key=lambda x: (x.similarity or 0, x.created_at), reverse=True)
    else:
        results.sort(key=lambda x: x.created_at, reverse=True)
    
    # Apply limit
    results = results[:limit]
    
    return SearchResponse(
        results=results,
        next_cursor=None,  # Simplified: no cursor pagination for search
        total_count=len(results),
    )
