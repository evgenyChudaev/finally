"""HTTP route modules for FinAlly.

Each router is a thin wrapper around a service module. The chat endpoint
lives in a separate task (LLM team); this package only owns the
non-LLM routes plus health.
"""
