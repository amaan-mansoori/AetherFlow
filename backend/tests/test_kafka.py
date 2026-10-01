"""Deterministic Kafka transport tests using fake clients."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest

from aetherflow.infrastructure.kafka import (
    KAFKA_MESSAGE_SCHEMA,
    KafkaConfigurationError,
    KafkaDispatcher,
    KafkaWorkerRunner,
    deserialize_dispatch_message,
    serialize_dispatch_message,
)
from aetherflow.jobs.dispatch import DispatchFailure, DispatchMessage
from aetherflow.jobs.worker import Worker


@dataclass
class FakeProducer:
    calls: list[tuple[str, bytes, bytes]]

    async def send_and_wait(self, topic: str, *, key: bytes, value: bytes) -> None:
        self.calls.append((topic, key, value))

    async def stop(self) -> None:
        return None


class FailingProducer(FakeProducer):
    async def send_and_wait(self, topic: str, *, key: bytes, value: bytes) -> None:
        raise RuntimeError("broker unavailable")


@dataclass
class FakeRecord:
    topic: str
    partition: int
    offset: int
    value: bytes
    key: bytes | None = None


@dataclass
class FakeConsumer:
    records: list[FakeRecord]
    commits: list[object]

    async def getone(self) -> FakeRecord:
        return self.records.pop(0)

    async def commit(self, offsets: object) -> None:
        self.commits.append(offsets)

    async def stop(self) -> None:
        return None


class FailingCommitConsumer(FakeConsumer):
    async def commit(self, offsets: object) -> None:
        raise RuntimeError("commit unavailable")


def sample_message() -> DispatchMessage:
    return DispatchMessage(UUID(int=7), 3, datetime(2026, 1, 1, tzinfo=UTC))


def test_dispatch_message_serialization_is_versioned_and_deterministic() -> None:
    payload = serialize_dispatch_message(sample_message())
    assert payload == serialize_dispatch_message(sample_message())
    assert f'"schema":"{KAFKA_MESSAGE_SCHEMA}"'.encode() in payload
    assert b'"job_version":3' in payload


def test_dispatch_message_round_trip() -> None:
    message = sample_message()
    assert deserialize_dispatch_message(serialize_dispatch_message(message)) == message


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b'{"schema":"aetherflow.job-dispatch.v1","schema_version":"v1"}',
        b'{"schema":"other","schema_version":"v1"}',
        b'{"schema":"aetherflow.job-dispatch.v1","schema_version":"v2"}',
        b'{"schema":"aetherflow.job-dispatch.v1","schema_version":"v1","job_id":"bad","job_version":1,"enqueued_at":"2026-01-01T00:00:00+00:00"}',
    ],
)
def test_invalid_dispatch_payload_is_rejected(payload: bytes) -> None:
    with pytest.raises(DispatchFailure):
        deserialize_dispatch_message(payload)


@pytest.mark.asyncio
async def test_kafka_dispatch_uses_job_id_key_and_serialized_value() -> None:
    producer = FakeProducer([])
    consumer = FakeConsumer([], [])
    dispatcher = KafkaDispatcher(topic="aetherflow.jobs", producer=producer, consumer=consumer)

    await dispatcher.dispatch(sample_message())

    assert producer.calls[0][0] == "aetherflow.jobs"
    assert producer.calls[0][1] == b"00000000-0000-0000-0000-000000000007"
    assert deserialize_dispatch_message(producer.calls[0][2]) == sample_message()


@pytest.mark.asyncio
async def test_kafka_dispatch_failure_is_explicit() -> None:
    dispatcher = KafkaDispatcher(
        topic="aetherflow.jobs",
        producer=FailingProducer([]),
        consumer=FakeConsumer([], []),
    )

    with pytest.raises(DispatchFailure, match="dispatch failed"):
        await dispatcher.dispatch(sample_message())


@pytest.mark.asyncio
async def test_kafka_receive_and_acknowledge_commit_offset() -> None:
    producer = FakeProducer([])
    consumer = FakeConsumer(
        [
            FakeRecord(
                "aetherflow.jobs",
                partition=2,
                offset=10,
                value=serialize_dispatch_message(sample_message()),
            )
        ],
        [],
    )
    dispatcher = KafkaDispatcher(topic="aetherflow.jobs", producer=producer, consumer=consumer)

    message = await dispatcher.receive()
    await dispatcher.acknowledge(message)

    assert len(consumer.commits) == 1
    committed = consumer.commits[0]
    assert len(committed) == 1
    offset_metadata = next(iter(committed.values()))
    assert offset_metadata.offset == 11


@pytest.mark.asyncio
async def test_kafka_receive_does_not_ack_malformed_payload() -> None:
    producer = FakeProducer([])
    consumer = FakeConsumer([FakeRecord("aetherflow.jobs", 0, 1, b"bad")], [])
    dispatcher = KafkaDispatcher(topic="aetherflow.jobs", producer=producer, consumer=consumer)

    with pytest.raises(DispatchFailure):
        await dispatcher.receive()
    assert consumer.commits == []


@pytest.mark.asyncio
async def test_kafka_offset_commit_failure_is_explicit() -> None:
    producer = FakeProducer([])
    consumer = FailingCommitConsumer(
        [FakeRecord("aetherflow.jobs", 0, 1, serialize_dispatch_message(sample_message()))],
        [],
    )
    dispatcher = KafkaDispatcher(topic="aetherflow.jobs", producer=producer, consumer=consumer)

    message = await dispatcher.receive()
    with pytest.raises(DispatchFailure, match="offset commit failed"):
        await dispatcher.acknowledge(message)


@pytest.mark.asyncio
async def test_producer_only_dispatcher_rejects_receive() -> None:
    dispatcher = KafkaDispatcher(
        topic="aetherflow.jobs",
        producer=FakeProducer([]),
    )

    with pytest.raises(DispatchFailure, match="consumer is not configured"):
        await dispatcher.receive()


@pytest.mark.asyncio
async def test_worker_runner_requires_consumer_dispatcher() -> None:
    dispatcher = KafkaDispatcher(topic="aetherflow.jobs", producer=FakeProducer([]))

    with pytest.raises(KafkaConfigurationError, match="requires a Kafka consumer"):
        KafkaWorkerRunner(dispatcher, Worker.__new__(Worker))
