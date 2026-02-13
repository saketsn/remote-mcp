from fastmcp import FastMCP
import os
import aiosqlite
import sqlite3
import logging
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MathMasterPro")

# SMART PATH FIX: Use a consistent path for the database.
# In production cloud environments, ensure you mount a persistent volume to this path.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "math_tuition_prod.db"))

mcp = FastMCP("MathMaster_Pro")

# --- Database Schema Setup ---
def init_db():
    """ Initializes the SQLite schema using standard synchronous sqlite3. """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            
            # Students Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    monthly_fee REAL DEFAULT 0.0,
                    joined_date DATE DEFAULT CURRENT_DATE
                )
            """)
            
            # Test Results Table
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
            conn.commit()
            logger.info(f" Database initialized at: {DB_PATH}")
    except Exception as e:
        logger.error(f"XXX DB Init Failed: {e}")
        raise

# Ensure DB is ready on startup
init_db()

# --- MCP Tools (Strictly Documented for Azure Foundry Schema) ---

@mcp.tool()
async def add_student(name: str, grade: str, monthly_fee: float) -> Dict[str, Any]:
    """
    Registers a new student into the tutoring system.
    
    Args:
        name: The full legal name of the student.
        grade: The current grade or class level (e.g., 'Grade 10').
        monthly_fee: The agreed upon monthly tuition fee amount.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO students (name, grade, monthly_fee) VALUES (?, ?, ?)",
                (name, grade, monthly_fee)
            )
            await db.commit()
            return {"status": "success", "student_id": cursor.lastrowid}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def record_test_score(
    student_id: int, 
    topic: str, 
    marks: float, 
    total: float, 
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Logs test marks for a student to track academic performance.
    
    Args:
        student_id: The unique ID of the student.
        topic: The specific subject or topic tested (e.g., 'Trigonometry').
        marks: The score obtained by the student.
        total: The maximum possible score.
        date: The date of the test (YYYY-MM-DD). Defaults to today.
    """
    test_date = date if date else datetime.now().strftime("%Y-%m-%d")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO test_results (student_id, test_date, topic, marks_obtained, total_marks) VALUES (?, ?, ?, ?, ?)",
                (student_id, test_date, topic, marks, total)
            )
            await db.commit()
            return {"status": "success", "message": f"Recorded score for {topic}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def delete_student(student_id: int) -> Dict[str, str]:
    """
    Permanently deletes a student and all their academic records.
    
    Args:
        student_id: The unique integer ID of the student to delete.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM students WHERE id = ?", (student_id,))
            await db.commit()
            return {"status": "success", "message": f"Student ID {student_id} deleted."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def get_student_report(student_id: int) -> Dict[str, Any]:
    """
    Retrieves full profile and academic history for a student.
    
    Args:
        student_id: The unique integer ID of the student.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM students WHERE id = ?", (student_id,)) as cur:
                profile = await cur.fetchone()
                if not profile: return {"status": "error", "message": "Student not found"}
                
            async with db.execute("SELECT * FROM test_results WHERE student_id = ?", (student_id,)) as cur:
                tests = [dict(row) for row in await cur.fetchall()]

            return {"profile": dict(profile), "academic_history": tests}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Run Settings ---
if __name__ == "__main__":
    # Required for cloud deployment (SSE transport and Port 8000)
    mcp.run(transport="sse", host="0.0.0.0", port=8000)