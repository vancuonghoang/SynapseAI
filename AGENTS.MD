# AGENTS.MD: The Constitution for the AI Trading System Project

## 1. Core Principles
- **1.1. Single Source of Truth:** All tasks derive from `BACKLOG.md`. All communication occurs in the relevant "Meeting Room" markdown file.
- **1.2. Context is King:** Before acting, you must read and comprehend the entire Contextual Task Bundle provided.
- **1.3. Maintain a Reasoning Log:** Your primary output is not just code, but also a detailed log of your thought process. Document decisions, considered alternatives, and struggles in the Meeting Room file. This is mandatory.

## 2. Git & Version Control
- **2.1. Feature Branches:** All work must be done on a feature branch named `feature/US-<ID>-<short-name>`.
- **2.2. Atomic Commits:** Commits should be small, logical, and have clear messages.

## 3. Coding Standards
- **3.1. Style:** All Python code must be formatted with `black`.
- **3.2. Security:** Never hardcode secrets. Use environment variables.

## 4. Testing Protocol
- **4.1. TDD is Encouraged:** All new business logic must be accompanied by unit tests.
- **4.2. Minimum Coverage:** Strive for >80% test coverage.
