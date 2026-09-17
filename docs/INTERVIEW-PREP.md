# Interview Preparation Notes

**Status:** Architecture / Specification Phase

Be prepared to explain:

- Why API and worker are separate processes while the codebase remains a modular monolith.
- Why PostgreSQL is authoritative and Kafka is transport/event distribution.
- How duplicate messages, concurrent submissions, state CAS, and unique results interact.
- What at-least-once means and why exactly-once is not claimed.
- How retries classify failures and prevent storms.
- Why cancellation is best effort with external providers.
- Why Redis outage must not lose job state.
- How provider abstraction protects business logic and enables deterministic tests.
- How trace context moves from HTTP through Kafka and inference.
- What evidence is required before claiming throughput or latency.
- Which features are deliberately out of scope and why.

The correct answer is always grounded in the documented invariants, measurements, and tradeoffs rather than technology-name memorization.

