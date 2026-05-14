"""Service-layer modules for FinAlly.

Services encapsulate cross-repo business logic (trade execution, watchlist
mutations) and are deliberately callable from outside the HTTP route layer
so the LLM executor can reuse them.
"""
