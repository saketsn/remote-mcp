from fastmcp import FastMCP
import os
import aiosqlite
import sqlite3
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MathMasterPro")

# CLOUD DEPLOYMENT FIX: Use /tmp for writable database in cloud environments
# Or use the environment variable if provided by your host
DB_PATH = os.environ.get("DATABASE_PATH", "/tmp/math_tuition_prod.db")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

# Initialize FastMCP - the name must be simple
mcp = FastMCP("MathMaster_Pro")

# --- Database Schema Setup ---
def init_db():
    """ Initializes the SQLite schema. """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
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
            
            # Fee Ledger Table
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
            logger.info(f"✅ Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ DB Init Failed: {e}")
        raise

# Initialize DB at module level so it runs during deployment
init_db()

# --- MCP Tools ---

@mcp.tool()
async def add_student(name: str, grade: str, monthly_fee: float) -> Dict[str, Any]:
    """Registers a new student. Returns the new student's ID."""
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
async def record_test_score(student_id: int, topic: str, marks: float, total: float, date: Optional[str] = None) -> Dict[str, Any]:
    """Logs test marks for a student. Date: YYYY-MM-DD."""
    test_date = date if date else datetime.now().strftime("%Y-%m-%d")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO test_results (student_id, test_date, topic, marks_obtained, total_marks) VALUES (?, ?, ?, ?, ?)",
                (student_id, test_date, topic, marks, total)
            )
            await db.commit()
            return {"status": "success", "message": f"Recorded {marks}/{total} for {topic}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def get_student_report(student_id: int) -> Dict[str, Any]:
    """Comprehensive look-up for student profile, academic, and financial history."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM students WHERE id = ?", (student_id,)) as cursor:
                profile = await cursor.fetchone()
                if not profile: return {"status": "error", "message": "ID not found"}
                
            async with db.execute("SELECT * FROM test_results WHERE student_id = ?", (student_id,)) as cursor:
                tests = [dict(row) for row in await cursor.fetchall()]

            return {"profile": dict(profile), "academic_history": tests}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Run Configuration ---
if __name__ == "__main__":
    # ESSENTIAL: 'sse' transport, 0.0.0.0 host, and explicit port for Foundry/Horizon
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=8000
    )