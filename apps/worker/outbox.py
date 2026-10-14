"""Asynchronous Transactional Outbox Worker and Event Dispatcher.

Adheres strictly to the Ponytail protocol:
- In-process event dispatcher with async subscription handlers.
- Polling worker with atomic state transitions (PENDING -> PROCESSING -> PUBLISHED / FAILED).
- Replaces external Kafka/RabbitMQ broker dependencies while preserving at-least-once delivery guarantees.
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
import logging
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.contracts import EventEnvelope, EventTypeEnum
from packages.domain.database import get_session_factory
from packages.domain.models import OutboxEvent, utc_now

logger = logging.getLogger("aegis.worker.outbox")

EventHandler = Callable[[EventEnvelope], Coroutine[Any, Any, None]]


class EventDispatcher:
    """In-memory event distribution hub for decoupling consumers from producers."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str | EventTypeEnum, handler: EventHandler) -> None:
        """Register an async event consumer for a given event type."""
        key = event_type.value if isinstance(event_type, EventTypeEnum) else event_type
        self._handlers[key].append(handler)
        logger.debug("Subscribed %s to %s", handler.__name__, key)

    async def dispatch(self, envelope: EventEnvelope) -> None:
        """Dispatch an event envelope to all subscribed handlers concurrently."""
        handlers = self._handlers.get(envelope.event_type.value, [])
        if not handlers:
            logger.debug("No registered handlers for event %s", envelope.event_type)
            return

        # Execute all handlers concurrently for maximal throughput
        results = await asyncio.gather(
            *(h(envelope) for h in handlers),
            return_exceptions=True,
        )

        for handler, res in zip(handlers, results):
            if isinstance(res, Exception):
                logger.error(
                    "Handler %s failed on event %s: %s",
                    handler.__name__,
                    envelope.event_id,
                    res,
                    exc_info=res,
                )
                raise res


# Global singleton dispatcher
_global_dispatcher = EventDispatcher()


def get_default_dispatcher() -> EventDispatcher:
    """Retrieve application-level event dispatcher singleton."""
    return _global_dispatcher


class OutboxWorker:
    """Asynchronous worker that polls the transactional outbox table and dispatches events."""

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession] | None = None,
        dispatcher: EventDispatcher | None = None,
        poll_interval_seconds: float = 0.5,
        batch_size: int = 50,
        max_retries: int = 3,
    ) -> None:
        self._session_maker = session_maker or get_session_factory()
        self._dispatcher = dispatcher or get_default_dispatcher()
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._stop_event = asyncio.Event()

    async def process_pending_batch(self) -> int:
        """Process a single batch of PENDING outbox events.
        
        Returns the number of events processed successfully.
        """
        async with self._session_maker() as session:
            # 1. Fetch unhandled events ordered by creation timestamp
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.status == "PENDING")
                .order_by(OutboxEvent.created_at.asc())
                .limit(self._batch_size)
            )
            result = await session.execute(stmt)
            events = result.scalars().all()

            if not events:
                return 0

            processed_count = 0

            for outbox_evt in events:
                try:
                    # 2. Mark event as PROCESSING
                    outbox_evt.status = "PROCESSING"
                    await session.flush()

                    # 3. Construct validated event envelope
                    envelope = EventEnvelope(
                        event_id=outbox_evt.event_id,
                        event_type=EventTypeEnum(outbox_evt.event_type),
                        tenant_id=outbox_evt.tenant_id,
                        occurred_at=outbox_evt.created_at,
                        producer="outbox_worker",
                        correlation_id=outbox_evt.correlation_id,
                        idempotency_key=outbox_evt.idempotency_key,
                        payload=outbox_evt.payload,
                    )

                    # 4. Dispatch to subscribers
                    await self._dispatcher.dispatch(envelope)

                    # 5. Mark PUBLISHED upon successful subscriber execution
                    outbox_evt.status = "PUBLISHED"
                    outbox_evt.processed_at = utc_now()
                    outbox_evt.error_message = None
                    processed_count += 1

                except Exception as exc:
                    outbox_evt.retry_count += 1
                    outbox_evt.error_message = str(exc)
                    if outbox_evt.retry_count >= self._max_retries:
                        outbox_evt.status = "FAILED"
                        logger.error("Outbox event %s permanently failed: %s", outbox_evt.id, exc)
                    else:
                        outbox_evt.status = "PENDING"  # Reset for retry
                        logger.warning("Outbox event %s retrying (%d/%d): %s", outbox_evt.id, outbox_evt.retry_count, self._max_retries, exc)

            await session.commit()
            return processed_count

    async def run(self) -> None:
        """Continuous background execution loop with clean shutdown support."""
        logger.info("OutboxWorker started (poll_interval=%.2fs)", self._poll_interval)
        while not self._stop_event.is_set():
            try:
                processed = await self.process_pending_batch()
                if processed == 0:
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)
                    except asyncio.TimeoutError:
                        pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Unexpected error in OutboxWorker loop: %s", e, exc_info=True)
                await asyncio.sleep(self._poll_interval)

        logger.info("OutboxWorker stopped gracefully.")

    def stop(self) -> None:
        """Signal worker to stop processing."""
        self._stop_event.set()
