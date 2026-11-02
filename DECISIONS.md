# Architecture & Engineering Decisions Log

This document records key decisions, assumptions, and rationales across implementation phases.

## 2026-11-02: Initial Setup & Monorepo Structure
- **Backend Environment**: Python 3.14 with asyncio, FastAPI, SQLAlchemy 2 (asyncio with `aiosqlite`), Pydantic v2.
- **Frontend Environment**: Vite + React 19 + TypeScript + Zustand + Phaser 3 + EasyStar.js.
- **LLM Abstraction**: Strict `LLMProvider` protocol with unified `ChatRequest` / `ChatResponse` model. Groq and Mock adapters isolate LLM calling so tests run 100% offline without credentials.
- **Storage**: SQLite with WAL mode for v1, schema design fully standard SQL to allow Postgres transition without code rewrites.
- **Event Bus & State Machine**: Append-only event store driving both backend scheduler/in-memory state and frontend live visualization via WebSockets with resume capability (`last_event_id`).
