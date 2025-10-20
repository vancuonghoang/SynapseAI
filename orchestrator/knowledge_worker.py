import sys
import os
from collections import Counter

# Ensure the parent directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text

# Ensure the parent directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from orchestrator.db import get_db_connection

def main():
    """Analyzes the logs to find patterns and suggest improvements."""
    print("\n--- Running Knowledge Distillation Worker ---")
    try:
        with get_db_connection() as conn:
            # Find agents that produce the most errors
            result = conn.execute(text("SELECT role FROM logs WHERE level = 'ERROR'"))
            errors = result.fetchall()
            
            if not errors:
                print("No ERROR logs found. The system is stable.")
                return

            error_counts = Counter([row[0] for row in errors])
            
            print("Found the following error patterns:")
            for role, count in error_counts.most_common():
                print(f"- Agent '{role}' produced {count} error(s).")
            
            most_common_agent = error_counts.most_common(1)[0][0]
            print(f"\n**Suggestion:** Review the implementation or prompts for the '{most_common_agent}' agent as it is the most frequent source of errors.")
            print("This could be a candidate for a new ADR (Architecture Decision Record) if the issue is systemic.")

    except Exception as e:
        print(f"[ERROR] Knowledge worker failed: {e}")

if __name__ == "__main__":
    main()