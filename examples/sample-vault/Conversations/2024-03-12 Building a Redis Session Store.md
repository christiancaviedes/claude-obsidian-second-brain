---
title: Building a Redis Session Store
date: 2024-03-12
topics: [redis, authentication, architecture]
---

# Building a Redis Session Store

## Summary

Compared database sessions with Redis and selected a TTL-based design for horizontal scaling.

## Decisions

- Use Redis for session storage.
- Refresh the 24-hour TTL on activity.

## Related

- [[Architecture MOC]]
