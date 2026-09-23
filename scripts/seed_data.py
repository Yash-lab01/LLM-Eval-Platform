"""Seed script to populate initial development data.

Creates 1 default consumer project and 3 benchmark prompts across key task types.
Validates all data structures through Pydantic v2 schemas before database insertion.
"""

import asyncio
import logging
import uuid

from sqlalchemy import select

from backend.core.database import AsyncSessionFactory
from backend.models.consumer import Consumer
from backend.models.prompt import Prompt
from backend.schemas.consumers import (
    EvalConsumerConfig,
    FeatureFlag,
    ScoringMetric,
    TaskType,
)
from backend.schemas.models import ModelID

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def seed() -> None:
    """Idempotently seed default consumer and sample prompts."""
    async with AsyncSessionFactory() as session:
        # 1. Seed Consumer: AI Terminal Agent
        consumer_name = "AI Terminal Agent"
        api_key = "eval_key_ai_terminal_agent_dev_001"
        consumer_id_str = "ai-terminal-agent"

        # Validate configuration through Pydantic v2
        config = EvalConsumerConfig(
            consumer_id=consumer_id_str,
            features=[
                FeatureFlag.BASIC_SCORING,
                FeatureFlag.OBSERVABILITY,
            ],
            models=[
                ModelID.GEMINI_3_5_FLASH,
                ModelID.GROQ_GPT_OSS_20B,
                ModelID.GROQ_QWEN_27B,
            ],
            task_type=TaskType.COMMAND_GENERATION,
            scoring_metrics=[
                ScoringMetric.BERT_SCORE,
                ScoringMetric.LATENCY,
                ScoringMetric.TOKEN_COUNT,
            ],
        )

        result = await session.execute(select(Consumer).where(Consumer.api_key == api_key))
        existing_consumer = result.scalar_one_or_none()

        if not existing_consumer:
            consumer = Consumer(
                id=uuid.uuid4(),
                name=consumer_name,
                api_key=api_key,
                config=config.model_dump(),
            )
            session.add(consumer)
            await session.flush()
            consumer_uuid = consumer.id
            logger.info(f"Created consumer: {consumer_name} (ID: {consumer_uuid})")
        else:
            consumer_uuid = existing_consumer.id
            logger.info(f"Consumer already exists: {consumer_name} (ID: {consumer_uuid})")

        # 2. Seed Prompts
        sample_prompts = [
            {
                "content": "Generate a PowerShell command to recursively find all .py files modified in the last 24 hours.",
                "task_type": TaskType.COMMAND_GENERATION.value,
                "tags": ["powershell", "filesystem", "terminal-agent"],
            },
            {
                "content": "Summarize the key architectural benefits of separating Redis into logical databases for cache, broker, and result backend.",
                "task_type": TaskType.SUMMARIZATION.value,
                "tags": ["redis", "architecture", "caching"],
            },
            {
                "content": "What are the primary differences between BERTScore semantic evaluation and n-gram overlap ROUGE-L scoring?",
                "task_type": TaskType.QUESTION_ANSWERING.value,
                "tags": ["nlp", "evaluation", "bertscore"],
            },
        ]

        for p_data in sample_prompts:
            stmt = select(Prompt).where(Prompt.content == p_data["content"])
            existing_prompt = (await session.execute(stmt)).scalar_one_or_none()
            if not existing_prompt:
                prompt = Prompt(
                    id=uuid.uuid4(),
                    consumer_id=consumer_uuid,
                    content=p_data["content"],
                    task_type=p_data["task_type"],
                    tags=p_data["tags"],
                    version=1,
                )
                session.add(prompt)
                logger.info(f"Created prompt for task: {p_data['task_type']}")
            else:
                logger.info(f"Prompt already exists for task: {p_data['task_type']}")

        await session.commit()
        logger.info("Database seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
