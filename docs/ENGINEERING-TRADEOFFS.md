# Engineering Tradeoffs

**Status:** Architecture / Specification Phase

| Choice | Benefit | Cost / accepted limitation |
|---|---|---|
| Modular monolith | Simple ownership and testing with clear boundaries | Less independent deployment than microservices |
| Kafka | Durable dispatch, consumer scaling, replayable events | Local and operational complexity |
| PostgreSQL authority | Strong queryability and consistency | Database can bottleneck |
| Redis ephemeral only | Fast limits/cache without split-brain job state | Degraded-mode policy required |
| At-least-once | Recoverable delivery without exactly-once illusion | Duplicate provider calls possible |
| Polling first | Simple, debuggable, proxy-friendly | Less real-time; SSE deferred |
| Mock provider | Deterministic CI and benchmarks | Does not represent external model quality |
| Kubernetes manifests before Helm | Fewer abstraction layers | More repetition across environments |
| One cloud | Focused, affordable deployment story | No multi-cloud portability claim |

