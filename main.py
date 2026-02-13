from fastmcp import FastMCP
import os
import aiosqlite
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- Configuration & Logging ---
# Setting up basic logging to track server activity and errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MathMasterPro")

# Persistence: DB is stored in the project folder to survive cloud redeploys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "math_tuition_prod.db")

# Initialize FastMCP Server
mcp = FastMCP("MathMaster_Pro_Production")

# --- Database Schema Setup ---

def init_db():
    """ Initializes the SQLite schema using standard synchronous sqlite3. """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # WAL mode improves performance for concurrent read/write operations
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # 1. Students: Primary table for personal details
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    monthly_fee REAL DEFAULT 0.0,
                    joined_date DATE DEFAULT CURRENT_DATE
                )
            """)
            
            # 2. Test Results: Linked to students via student_id
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
            
            # 3. Fee Ledger: Tracks financial history
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
            logger.info(f" Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f" XXX Database initialization failed: {e}")
        raise

# Run DB init on startup
init_db()

# --- MCP Tools ---

@mcp.tool()
async def add_student(name: str, grade: str, monthly_fee: float) -> Dict[str, Any]:
    """
    Registers a new student into the system.
    Returns the new student's ID.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO students (name, grade, monthly_fee) VALUES (?, ?, ?)",
                (name, grade, monthly_fee)
            )
            await db.commit()
            return {"status": "success", "student_id": cursor.lastrowid, "message": f"Student {name} added."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def record_test_score(student_id: int, topic: str, marks: float, total: float, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Logs test marks for a student. 
    Date should be YYYY-MM-DD. If omitted, today's date is used.
    """
    test_date = date if date else datetime.now().strftime("%Y-%m-%d")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO test_results (student_id, test_date, topic, marks_obtained, total_marks) VALUES (?, ?, ?, ?, ?)",
                (student_id, test_date, topic, marks, total)
            )
            await db.commit()
            return {"status": "success", "message": f"Recorded {marks}/{total} for {topic} on {test_date}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def record_fee_payment(student_id: int, amount: float, month: str) -> Dict[str, Any]:
    """
    Records a tuition fee payment. 
    Month should be descriptive, e.g., 'March 2026'.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO fee_records (student_id, amount, payment_date, month_covered) VALUES (?, ?, ?, ?)",
                (student_id, amount, today, month)
            )
            await db.commit()
            return {"status": "success", "message": f"Payment of {amount} for {month} recorded."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def get_student_full_detail(student_id: int) -> Dict[str, Any]:
    """
    Comprehensive look-up for a student.
    Combines profile, all test scores, and all payment history in one view.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            # Fetch Profile
            async with db.execute("SELECT * FROM students WHERE id = ?", (student_id,)) as cursor:
                profile = await cursor.fetchone()
                if not profile:
                    return {"status": "error", "message": "Student ID not found."}
                student_data = dict(profile)

            # Fetch Test History
            async with db.execute("SELECT test_date, topic, marks_obtained, total_marks FROM test_results WHERE student_id = ? ORDER BY test_date DESC", (student_id,)) as cursor:
                tests = [dict(row) for row in await cursor.fetchall()]

            # Fetch Fee History
            async with db.execute("SELECT amount, payment_date, month_covered FROM fee_records WHERE student_id = ? ORDER BY payment_date DESC", (student_id,)) as cursor:
                fees = [dict(row) for row in await cursor.fetchall()]

            return {
                "status": "success",
                "student_profile": student_data,
                "academic_history": tests,
                "financial_history": fees
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def list_students_summary() -> List[Dict[str, Any]]:
    """
    Returns a quick list of all registered students with their current grade.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, name, grade, joined_date FROM students") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

# --- Resources ---

@mcp.resource("tuition://stats")
async def get_total_stats() -> str:
    """ Provides a high-level summary of the tuition business. """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM students") as c:
            count = (await c.fetchone())[0]
        async with db.execute("SELECT SUM(amount) FROM fee_records") as c:
            revenue = (await c.fetchone())[0] or 0.0
            
    return f"MathMaster Pro currently manages {count} students with total collected revenue of {revenue}."

if __name__ == "__main__":
    # Launch the server
    mcp.run()