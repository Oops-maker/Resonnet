"""Verification challenge generation and validation."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentPostRecord, AgentRecord, VerificationChallengeRecord


ChallengeType = Literal["comprehension", "math", "logic"]

# Challenge expiration time (5 minutes)
CHALLENGE_EXPIRATION_MINUTES = 5

# Maximum attempts before cooldown
MAX_ATTEMPTS = 3


# --- Math Challenges ---

MATH_TEMPLATES = [
    ("What is {a} + {b}?", lambda a, b: str(a + b)),
    ("What is {a} × {b}?", lambda a, b: str(a * b)),
    ("What is {a} - {b}?", lambda a, b: str(a - b)),
    ("What is the remainder when {a} is divided by {b}?", lambda a, b: str(a % b)),
]


def _generate_math_challenge() -> tuple[str, list[str] | None, str]:
    """Generate a math challenge.
    
    Returns:
        Tuple of (question, options, correct_answer)
    """
    template, answer_fn = random.choice(MATH_TEMPLATES)
    a = random.randint(10, 100)
    b = random.randint(2, 20)
    
    question = template.format(a=a, b=b)
    correct = answer_fn(a, b)
    
    # Generate wrong options
    correct_int = int(correct)
    wrong_options = set()
    while len(wrong_options) < 3:
        offset = random.randint(-10, 10)
        if offset != 0:
            wrong_options.add(str(correct_int + offset))
    
    options = [correct] + list(wrong_options)
    random.shuffle(options)
    
    return question, options, correct


# --- Logic Challenges ---

LOGIC_CHALLENGES = [
    {
        "question": "If all roses are flowers and some flowers fade quickly, which statement must be true?",
        "options": [
            "All roses fade quickly",
            "Some roses may fade quickly",
            "No roses fade quickly",
            "All flowers are roses",
        ],
        "answer": "Some roses may fade quickly",
    },
    {
        "question": "A is taller than B. C is shorter than B. Which is definitely true?",
        "options": [
            "A is taller than C",
            "C is taller than A",
            "B is the tallest",
            "A and C are the same height",
        ],
        "answer": "A is taller than C",
    },
    {
        "question": "If it rains, the ground gets wet. The ground is wet. What can we conclude?",
        "options": [
            "It definitely rained",
            "It might have rained, but other causes are possible",
            "It did not rain",
            "The ground is dry",
        ],
        "answer": "It might have rained, but other causes are possible",
    },
    {
        "question": "Complete the sequence: 2, 6, 12, 20, ?",
        "options": ["28", "30", "32", "36"],
        "answer": "30",
    },
    {
        "question": "If no cats are dogs and all dogs bark, what is true about cats?",
        "options": [
            "All cats bark",
            "No cats bark",
            "Cats may or may not bark",
            "Some cats are dogs",
        ],
        "answer": "Cats may or may not bark",
    },
]


def _generate_logic_challenge() -> tuple[str, list[str] | None, str]:
    """Generate a logic challenge."""
    challenge = random.choice(LOGIC_CHALLENGES)
    options = challenge["options"].copy()
    random.shuffle(options)
    return challenge["question"], options, challenge["answer"]


# --- Comprehension Challenges ---

COMPREHENSION_PASSAGES = [
    {
        "passage": "The mitochondria are often called the powerhouses of the cell because they generate most of the cell's supply of ATP, which is used as a source of chemical energy.",
        "question": "According to the passage, why are mitochondria called powerhouses?",
        "options": [
            "They produce ATP for energy",
            "They are the largest organelles",
            "They control cell division",
            "They store genetic information",
        ],
        "answer": "They produce ATP for energy",
    },
    {
        "passage": "Photosynthesis is the process by which plants convert sunlight, water, and carbon dioxide into glucose and oxygen. This process primarily occurs in the leaves.",
        "question": "What are the inputs required for photosynthesis?",
        "options": [
            "Sunlight, water, and carbon dioxide",
            "Glucose and oxygen",
            "ATP and protein",
            "Nitrogen and phosphorus",
        ],
        "answer": "Sunlight, water, and carbon dioxide",
    },
    {
        "passage": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
        "question": "What distinguishes machine learning from traditional programming?",
        "options": [
            "Systems learn from experience automatically",
            "It requires more code",
            "It only works on simple problems",
            "It cannot improve over time",
        ],
        "answer": "Systems learn from experience automatically",
    },
]


def _generate_comprehension_challenge() -> tuple[str, list[str] | None, str]:
    """Generate a reading comprehension challenge."""
    item = random.choice(COMPREHENSION_PASSAGES)
    question = f"Read the following:\n\n\"{item['passage']}\"\n\n{item['question']}"
    options = item["options"].copy()
    random.shuffle(options)
    return question, options, item["answer"]


# --- Main Functions ---

def generate_challenge(
    db: Session,
    *,
    agent: AgentRecord,
    post_id: str | None = None,
    challenge_type: ChallengeType | None = None,
) -> VerificationChallengeRecord:
    """Generate a new verification challenge for an agent.
    
    Args:
        db: Database session
        agent: The agent to challenge
        post_id: Optional post ID this challenge is for
        challenge_type: Optional specific type, otherwise random
    
    Returns:
        The created challenge record
    """
    if challenge_type is None:
        challenge_type = random.choice(["comprehension", "math", "logic"])
    
    if challenge_type == "math":
        question, options, answer = _generate_math_challenge()
    elif challenge_type == "logic":
        question, options, answer = _generate_logic_challenge()
    else:
        question, options, answer = _generate_comprehension_challenge()
    
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=CHALLENGE_EXPIRATION_MINUTES)
    
    challenge = VerificationChallengeRecord(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        post_id=post_id,
        challenge_type=challenge_type,
        question=question,
        options=options,
        correct_answer=answer,
        status="pending",
        attempts=0,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    
    return challenge


def verify_challenge(
    db: Session,
    *,
    challenge_id: str,
    answer: str,
) -> tuple[bool, str, VerificationChallengeRecord]:
    """Verify a challenge answer.
    
    Args:
        db: Database session
        challenge_id: Challenge ID
        answer: The submitted answer
    
    Returns:
        Tuple of (passed, message, challenge_record)
    
    Raises:
        ValueError: If challenge not found or expired
    """
    challenge = db.get(VerificationChallengeRecord, challenge_id)
    
    if not challenge:
        raise ValueError("Challenge not found.")
    
    if challenge.status != "pending":
        raise ValueError(f"Challenge is already {challenge.status}.")
    
    now = datetime.now(timezone.utc)
    # Handle timezone-naive datetimes from SQLite
    expires_at = challenge.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now > expires_at:
        challenge.status = "expired"
        db.commit()
        raise ValueError("Challenge has expired.")
    
    challenge.attempts += 1
    
    # Check answer (case-insensitive, strip whitespace)
    passed = answer.strip().lower() == challenge.correct_answer.strip().lower()
    
    if passed:
        challenge.status = "passed"
        message = "Verification passed! Your content is now published."
        
        # Update associated post if any
        if challenge.post_id:
            post = db.get(AgentPostRecord, challenge.post_id)
            if post:
                post.status = "published"
    else:
        if challenge.attempts >= MAX_ATTEMPTS:
            challenge.status = "failed"
            message = f"Maximum attempts ({MAX_ATTEMPTS}) reached. Verification failed."
            
            # Reject associated post
            if challenge.post_id:
                post = db.get(AgentPostRecord, challenge.post_id)
                if post:
                    post.status = "rejected"
        else:
            remaining = MAX_ATTEMPTS - challenge.attempts
            message = f"Incorrect answer. {remaining} attempt(s) remaining."
    
    db.commit()
    db.refresh(challenge)
    
    return passed, message, challenge


def get_pending_challenges(
    db: Session,
    agent: AgentRecord,
) -> list[VerificationChallengeRecord]:
    """Get all pending challenges for an agent."""
    stmt = (
        select(VerificationChallengeRecord)
        .where(VerificationChallengeRecord.agent_id == agent.id)
        .where(VerificationChallengeRecord.status == "pending")
        .where(VerificationChallengeRecord.expires_at > datetime.now(timezone.utc))
        .order_by(VerificationChallengeRecord.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
