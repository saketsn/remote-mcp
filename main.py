# from fastmcp import FastMCP
# import os
# import aiosqlite
# import sqlite3
# import logging
# import tempfile
# from datetime import datetime
# from typing import List, Dict, Any, Optional

# # --- Configuration & Logging ---
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("MathMasterPro")

# # SMART PATH FIX: Works on Windows local and Horizon Cloud
# # 1. Checks for an environment variable (for production)
# # 2. Defaults to the system's native temp directory (C:\Users\... on Win, /tmp on Linux)
# TEMP_DIR = tempfile.gettempdir()
# DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(TEMP_DIR, "math_tuition_prod.db"))

# # Initialize FastMCP Server object
# mcp = FastMCP("MathMaster_Pro")

# # --- Database Schema Setup ---
# def init_db():
#     """ Initializes the SQLite schema using standard synchronous sqlite3. """
#     try:
#         # Connect to the resolved path
#         with sqlite3.connect(DB_PATH) as conn:
#             conn.execute("PRAGMA journal_mode=WAL")
#             cursor = conn.cursor()
            
#             # 1. Students Registry
#             cursor.execute("""
#                 CREATE TABLE IF NOT EXISTS students(
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     name TEXT NOT NULL,
#                     grade TEXT NOT NULL,
#                     monthly_fee REAL DEFAULT 0.0,
#                     joined_date DATE DEFAULT CURRENT_DATE
#                 )
#             """)
            
#             # 2. Academic Progress Tracking
#             cursor.execute("""
#                 CREATE TABLE IF NOT EXISTS test_results(
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     student_id INTEGER,
#                     test_date DATE NOT NULL,
#                     topic TEXT NOT NULL,
#                     marks_obtained REAL NOT NULL,
#                     total_marks REAL NOT NULL,
#                     FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
#                 )
#             """)
            
#             # 3. Financial Ledger
#             cursor.execute("""
#                 CREATE TABLE IF NOT EXISTS fee_records(
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     student_id INTEGER,
#                     amount REAL NOT NULL,
#                     payment_date DATE NOT NULL,
#                     month_covered TEXT NOT NULL,
#                     FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
#                 )
#             """)
#             conn.commit()
#             logger.info(f" Database ready at: {DB_PATH}")
#     except Exception as e:
#         logger.error(f"XX DB Init Failed: {e}")
#         raise

# # Run initialization during module load
# init_db()

# # --- MCP Tools ---

# @mcp.tool()
# async def add_student(name: str, grade: str, monthly_fee: float) -> Dict[str, Any]:
#     """Registers a new student. Returns the generated student_id."""
#     try:
#         async with aiosqlite.connect(DB_PATH) as db:
#             cursor = await db.execute(
#                 "INSERT INTO students (name, grade, monthly_fee) VALUES (?, ?, ?)",
#                 (name, grade, monthly_fee)
#             )
#             await db.commit()
#             return {"status": "success", "student_id": cursor.lastrowid}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}

# @mcp.tool()
# async def delete_student(student_id: int) -> dict:
#     """
#     Permanently deletes a student and all their associated records 
#     (scores and fees) from the database.
#     """
#     try:
#         async with aiosqlite.connect(DB_PATH) as db:
#             # Check if student exists first
#             async with db.execute("SELECT name FROM students WHERE id = ?", (student_id,)) as cursor:
#                 student = await cursor.fetchone()
#                 if not student:
#                     return {"status": "error", "message": f"Student ID {student_id} not found."}
                
#             # Perform deletion
#             await db.execute("DELETE FROM students WHERE id = ?", (student_id,))
#             await db.commit()
#             return {"status": "success", "message": f"Student {student[0]} and all records deleted."}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}

# @mcp.tool()
# async def record_test_score(student_id: int, topic: str, marks: float, total: float, date: Optional[str] = None) -> Dict[str, Any]:
#     """Logs test marks. Date format: YYYY-MM-DD (defaults to today)."""
#     test_date = date if date else datetime.now().strftime("%Y-%m-%d")
#     try:
#         async with aiosqlite.connect(DB_PATH) as db:
#             await db.execute(
#                 "INSERT INTO test_results (student_id, test_date, topic, marks_obtained, total_marks) VALUES (?, ?, ?, ?, ?)",
#                 (student_id, test_date, topic, marks, total)
#             )
#             await db.commit()
#             return {"status": "success", "message": f"Recorded score for {topic}."}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}

# @mcp.tool()
# async def get_student_report(student_id: int) -> Dict[str, Any]:
#     """Retrieves full profile, academic trends, and payment history for a student."""
#     try:
#         async with aiosqlite.connect(DB_PATH) as db:
#             db.row_factory = aiosqlite.Row
#             # Fetch profile
#             async with db.execute("SELECT * FROM students WHERE id = ?", (student_id,)) as cur:
#                 profile = await cur.fetchone()
#                 if not profile: return {"status": "error", "message": "Student not found"}
                
#             # Fetch scores
#             async with db.execute("SELECT * FROM test_results WHERE student_id = ?", (student_id,)) as cur:
#                 tests = [dict(row) for row in await cur.fetchall()]

#             return {"profile": dict(profile), "academic_history": tests}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}

# # --- Run Settings ---
# if __name__ == "__main__":
#     # Required settings for Foundry: sse transport and specific port
#     mcp.run(
#         transport="sse",
#         host="0.0.0.0",
#         port=8000
#     )


from fastmcp import FastMCP
import os
import aiosqlite
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MathMasterPro")

# PERMANENT STORAGE FIX: 
# Using the script's directory ensures the database is stored alongside your code.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Default to the application folder for persistence, but allow override via Env Var
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "math_tuition_prod.db"))

logger.info(f" Database location: {DB_PATH}")

# Initialize FastMCP Server object
mcp = FastMCP("MathMaster_Pro")

# --- Database Schema Setup ---
def init_db():
    """ Initializes the SQLite schema using standard synchronous sqlite3. """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            # Foreign keys ensure that deleting a student also deletes their scores/fees
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
            logger.info("=== Database schema verified/initialized.")
    except Exception as e:
        logger.error(f"XXX DB Init Failed: {e}")
        raise

# Run initialization during module load
init_db()

# --- MCP Tools ---

@mcp.tool()
async def add_student(name: str, grade: str, monthly_fee: float) -> Dict[str, Any]:
    """Registers a new student. Returns the generated student_id."""
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
async def delete_student(student_id: int) -> dict:
    """Permanently deletes a student and all their associated records from the database."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name FROM students WHERE id = ?", (student_id,)) as cursor:
                student = await cursor.fetchone()
                if not student:
                    return {"status": "error", "message": f"Student ID {student_id} not found."}
                
            await db.execute("DELETE FROM students WHERE id = ?", (student_id,))
            await db.commit()
            return {"status": "success", "message": f"Student {student[0]} and all records deleted."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def record_test_score(student_id: int, topic: str, marks: float, total: float, date: Optional[str] = None) -> Dict[str, Any]:
    """Logs test marks. Date format: YYYY-MM-DD (defaults to today)."""
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
async def get_student_report(student_id: int) -> Dict[str, Any]:
    """Retrieves full profile, academic trends, and payment history for a student."""
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
    # Settings for Foundry: sse transport and port 8000
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=8000
    )