from fastmcp import FastMCP
import os
import aiosqlite
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MathMasterPro")

# PRODUCTION STORAGE: Using script directory for persistence on Azure Foundry.
# This ensures data survives reboots if a persistent volume is attached.
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
DB_PATH: str = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "math_tuition_prod.db"))

logger.info(f" Database initialized at: {DB_PATH}")

# Initialize FastMCP Server object
mcp = FastMCP("MathMaster_Pro_Production")

# --- Database Schema Setup ---
def init_db() -> None:
    """Initializes the SQLite schema with WAL mode and foreign key constraints."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            
            # 1. Students Registry
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    monthly_fee REAL DEFAULT 0.0,
                    joined_date DATE DEFAULT CURRENT_DATE
                )
            """)
            
            # 2. Academic Progress Tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_results(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    test_date DATE NOT NULL,
                    topic TEXT NOT NULL,
                    marks_obtained REAL NOT NULL,
                    total_marks REAL NOT NULL,
                    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
                )
            """)
            
            # 3. Financial Ledger
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fee_records(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    amount REAL NOT NULL,
                    payment_date DATE NOT NULL,
                    month_covered TEXT NOT NULL,
                    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
                )
            """)
            conn.commit()
            logger.info(" Database schema verified.")
    except Exception as e:
        logger.error(f"XXX DB Init Failed: {e}")
        raise

# Run initialization during module load
init_db()

# --- MCP Tools with Strict Type Annotations ---

@mcp.tool()
async def add_student(name: str, grade: str, monthly_fee: float) -> Dict[str, Any]:
    """Registers a new student. Returns a status dictionary with the student_id."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO students (name, grade, monthly_fee) VALUES (?, ?, ?)",
                (name, grade, monthly_fee)
            )
            await db.commit()
            return {
                "status": "success", 
                "student_id": cursor.lastrowid, 
                "message": f"Successfully onboarded {name}"
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def delete_student(student_id: int) -> Dict[str, str]:
    """Permanently deletes a student and all associated academic/financial records."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name FROM students WHERE id = ?", (student_id,)) as cursor:
                student = await cursor.fetchone()
                if not student:
                    return {"status": "error", "message": f"Student ID {student_id} not found."}
                
            await db.execute("DELETE FROM students WHERE id = ?", (student_id,))
            await db.commit()
            return {"status": "success", "message": f"Student {student[0]} and all associated data deleted."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def record_test_score(
    student_id: int, 
    topic: str, 
    marks: float, 
    total: float, 
    date: Optional[str] = None
) -> Dict[str, str]:
    """Logs academic test marks. Date format: YYYY-MM-DD (defaults to today)."""
    test_date: str = date if date else datetime.now().strftime("%Y-%m-%d")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO test_results (student_id, test_date, topic, marks_obtained, total_marks) VALUES (?, ?, ?, ?, ?)",
                (student_id, test_date, topic, marks, total)
            )
            await db.commit()
            return {"status": "success", "message": f"Recorded score for {topic} on {test_date}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def get_student_report(student_id: int) -> Dict[str, Any]:
    """Retrieves a comprehensive student report including profile and academic history."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM students WHERE id = ?", (student_id,)) as cur:
                profile = await cur.fetchone()
                if not profile: 
                    return {"status": "error", "message": "Student record not found."}
                
            async with db.execute("SELECT * FROM test_results WHERE student_id = ? ORDER BY test_date DESC", (student_id,)) as cur:
                tests: List[Dict[str, Any]] = [dict(row) for row in await cur.fetchall()]

            return {
                "status": "success",
                "profile": dict(profile), 
                "academic_history": tests
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Run Settings ---
if __name__ == "__main__":
    # Required settings for Azure Foundry / Horizon:
    # Uses SSE transport for persistent remote connections via Port 8000
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=8000
    )