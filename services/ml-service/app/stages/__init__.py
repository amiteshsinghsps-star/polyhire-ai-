"""PolyHire ML pipeline stages.

Each module here is a self-contained stage of the candidate-discovery
pipeline. Stages are intentionally decoupled — they take dicts/dataclasses
in and return dicts out — so the orchestrator in app/pipeline.py can wire
them together and so each can be unit-tested in isolation.
"""
