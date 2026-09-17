# Scaling Strategy

**Status:** Architecture / Specification Phase

Scale API replicas independently from workers. Worker replicas share a Kafka consumer group; useful parallelism is bounded by topic partitions and downstream/provider limits. Scheduler leadership/leases prevent duplicate scheduling if it is independently deployed. PostgreSQL connection pools, indexes, and transaction duration are capacity constraints to measure. Redis and Kafka capacity are monitored rather than assumed infinite.

Scale triggers are queue lag/age, request saturation, error rate, provider limits, and resource utilization. Autoscaling thresholds are environment configuration and require load-test evidence. Vertical scaling and query optimization precede service decomposition. Multi-tenant partitioning and sharding are out of scope.

