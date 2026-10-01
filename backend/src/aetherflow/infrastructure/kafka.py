"""Kafka transport adapter for broker-neutral job dispatch messages."""

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from importlib import import_module
from typing import Protocol, Self, cast
from uuid import UUID

from aetherflow.config.settings import Settings
from aetherflow.jobs.dispatch import (
    DispatchFailure,
    DispatchMessage,
    JobDispatcher,
    TransientDispatchFailure,
)
from aetherflow.jobs.worker import Worker

KAFKA_MESSAGE_SCHEMA = "aetherflow.job-dispatch.v1"


class KafkaConfigurationError(RuntimeError):
    """Raised when the Kafka client dependency or configuration is unusable."""


class KafkaProducer(Protocol):
    async def start(self) -> None:
        """Start the producer."""

    async def send_and_wait(self, topic: str, *, key: bytes, value: bytes) -> object:
        """Publish one message and wait for the producer acknowledgement."""

    async def stop(self) -> None:
        """Stop the producer."""


class KafkaRecord(Protocol):
    topic: str
    partition: int
    offset: int
    key: bytes | None
    value: bytes | str


class KafkaConsumer(Protocol):
    async def start(self) -> None:
        """Start the consumer."""

    async def getone(self) -> KafkaRecord:
        """Receive the next record from the assigned consumer group."""

    async def commit(self, offsets: Mapping[object, object]) -> None:
        """Commit explicit offsets."""

    async def stop(self) -> None:
        """Stop the consumer."""


def serialize_dispatch_message(message: DispatchMessage) -> bytes:
    """Serialize a dispatch message into deterministic UTF-8 JSON."""

    payload = {
        "schema": KAFKA_MESSAGE_SCHEMA,
        "schema_version": message.schema_version,
        "job_id": str(message.job_id),
        "job_version": message.job_version,
        "enqueued_at": message.enqueued_at.isoformat(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def deserialize_dispatch_message(payload: bytes | str) -> DispatchMessage:
    """Validate and deserialize a Kafka dispatch payload."""

    try:
        raw = json.loads(payload)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DispatchFailure("Kafka message is not valid JSON.") from exc
    if not isinstance(raw, dict):
        raise DispatchFailure("Kafka message must be a JSON object.")
    if raw.get("schema") != KAFKA_MESSAGE_SCHEMA:
        raise DispatchFailure("Kafka message has an unsupported schema.")
    if raw.get("schema_version") != "v1":
        raise DispatchFailure("Kafka message has an unsupported schema version.")
    try:
        job_id = UUID(raw["job_id"])
        job_version = raw["job_version"]
        enqueued_at = datetime.fromisoformat(raw["enqueued_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DispatchFailure("Kafka message has invalid dispatch fields.") from exc
    if not isinstance(job_version, int) or isinstance(job_version, bool) or job_version < 1:
        raise DispatchFailure("Kafka message has an invalid job version.")
    if enqueued_at.tzinfo is None:
        raise DispatchFailure("Kafka message enqueued_at must include a timezone.")
    return DispatchMessage(job_id, job_version, enqueued_at, "v1")


class KafkaDispatcher(JobDispatcher):
    """Async Kafka producer/consumer adapter with explicit offset commits."""

    def __init__(
        self,
        *,
        topic: str,
        producer: KafkaProducer,
        consumer: KafkaConsumer | None = None,
    ) -> None:
        if not topic.strip():
            raise KafkaConfigurationError("Kafka topic must not be blank.")
        self._topic = topic
        self._producer = producer
        self._consumer = consumer
        self._pending_record: KafkaRecord | None = None

    @property
    def has_consumer(self) -> bool:
        """Return whether this adapter can receive and acknowledge messages."""

        return self._consumer is not None

    @classmethod
    async def create(cls, settings: Settings) -> Self:
        """Create and start real aiokafka clients from application settings."""

        try:
            kafka = import_module("aiokafka")
        except ImportError as exc:
            raise KafkaConfigurationError(
                "aiokafka is required to create a Kafka dispatcher."
            ) from exc
        producer_factory = cast(Callable[..., KafkaProducer], kafka.AIOKafkaProducer)
        producer = producer_factory(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            client_id=settings.kafka_client_id,
            enable_idempotence=settings.kafka_producer_enable_idempotence,
            acks="all",
        )
        await producer.start()
        return cls(topic=settings.kafka_topic, producer=producer)

    @classmethod
    async def create_worker_dispatcher(cls, settings: Settings) -> Self:
        """Create a producer/consumer adapter for an independent worker runtime."""

        try:
            kafka = import_module("aiokafka")
        except ImportError as exc:
            raise KafkaConfigurationError(
                "aiokafka is required to create a Kafka dispatcher."
            ) from exc
        producer_factory = cast(Callable[..., KafkaProducer], kafka.AIOKafkaProducer)
        consumer_factory = cast(Callable[..., KafkaConsumer], kafka.AIOKafkaConsumer)
        producer = producer_factory(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            client_id=settings.kafka_client_id,
            enable_idempotence=settings.kafka_producer_enable_idempotence,
            acks="all",
        )
        consumer = consumer_factory(
            settings.kafka_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_consumer_group,
            client_id=settings.kafka_client_id,
            enable_auto_commit=False,
            auto_offset_reset=settings.kafka_auto_offset_reset,
        )
        await producer.start()
        try:
            await consumer.start()
        except Exception:
            await producer.stop()
            raise
        return cls(topic=settings.kafka_topic, producer=producer, consumer=consumer)

    async def close(self) -> None:
        """Stop clients during graceful worker shutdown."""

        consumer_error: BaseException | None = None
        producer_error: BaseException | None = None
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except BaseException as exc:
                consumer_error = exc
        try:
            await self._producer.stop()
        except BaseException as exc:
            producer_error = exc
        if consumer_error is not None:
            raise consumer_error
        if producer_error is not None:
            raise producer_error

    async def dispatch(self, message: DispatchMessage) -> None:
        try:
            await self._producer.send_and_wait(
                self._topic,
                key=str(message.job_id).encode("ascii"),
                value=serialize_dispatch_message(message),
            )
        except Exception as exc:
            raise TransientDispatchFailure("Kafka dispatch failed.") from exc

    async def receive(self) -> DispatchMessage:
        if self._consumer is None:
            raise DispatchFailure("Kafka consumer is not configured.")
        try:
            record = await self._consumer.getone()
            message = deserialize_dispatch_message(record.value)
        except DispatchFailure:
            raise
        except Exception as exc:
            raise DispatchFailure("Kafka receive failed.") from exc
        self._pending_record = record
        return message

    async def acknowledge(self, message: DispatchMessage) -> None:
        if self._consumer is None:
            raise DispatchFailure("Kafka consumer is not configured.")
        record = self._pending_record
        if record is None:
            raise DispatchFailure("No received Kafka message is pending acknowledgement.")
        try:
            structs = import_module("aiokafka.structs")
            offset_factory = cast(Callable[..., object], structs.OffsetAndMetadata)
            partition_factory = cast(Callable[..., object], structs.TopicPartition)

            await self._consumer.commit(
                {
                    partition_factory(record.topic, record.partition): offset_factory(
                        record.offset + 1, ""
                    ),
                }
            )
        except Exception as exc:
            raise DispatchFailure("Kafka offset commit failed.") from exc
        finally:
            self._pending_record = None


class KafkaWorkerRunner:
    """Run the existing Worker against Kafka until cancellation."""

    def __init__(self, dispatcher: KafkaDispatcher, worker: Worker) -> None:
        if not dispatcher.has_consumer:
            raise KafkaConfigurationError("A worker runner requires a Kafka consumer.")
        self._worker = worker

    async def run_once(self) -> None:
        """Process one message; failures remain unacknowledged for redelivery."""

        await self._worker.run_once()

    async def run_forever(self) -> None:
        """Process messages until the runtime is cancelled."""

        while True:
            await self.run_once()
