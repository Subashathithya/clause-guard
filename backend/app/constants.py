"""Shared module-level constants for the ClauseGuard API."""

APP_VERSION = "2.0.0"

#: Agents that make up the analysis pipeline (order of execution).
PIPELINE_AGENTS = ["Extractor", "Comparator", "Ranker", "Negotiator"]