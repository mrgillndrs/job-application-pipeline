"""
Database utility functions for Job Matching Pipeline.
Handles connections, queries, inserts, and common database operations.
"""

import pyodbc
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
import json
from src.config import get_db_connection_string


def get_connection() -> pyodbc.Connection:
    """
    Create and return a database connection.
    
    Returns:
        pyodbc.Connection: Active database connection
        
    Raises:
        pyodbc.Error: If connection fails
    """
    try:
        conn_str = get_db_connection_string()
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as e:
        print(f"❌ Database connection failed: {e}")
        raise


def execute_query(query: str, params: Optional[Tuple] = None, fetch: bool = True) -> Optional[List[Tuple]]:
    """
    Execute a SELECT query and return results.
    
    Args:
        query: SQL query string
        params: Optional tuple of parameters for parameterized queries
        fetch: Whether to fetch results (False for INSERT/UPDATE/DELETE)
        
    Returns:
        List of tuples (rows) if fetch=True, None otherwise
        
    Example:
        rows = execute_query("SELECT * FROM staging.raw_jobs WHERE company = ?", ("Google",))
    """
    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            results = cursor.fetchall()
            return results
        else:
            conn.commit()
            return None
            
    except pyodbc.Error as e:
        print(f"❌ Query execution failed: {e}")
        print(f"Query: {query}")
        if conn:
            conn.rollback()
        raise
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def execute_query_df(query: str, params: Optional[Tuple] = None) -> pd.DataFrame:
    """
    Execute a SELECT query and return results as a pandas DataFrame.
    
    Args:
        query: SQL query string
        params: Optional tuple of parameters for parameterized queries
        
    Returns:
        pandas DataFrame with query results
        
    Example:
        df = execute_query_df("SELECT * FROM staging.raw_jobs")
    """
    conn = None
    
    try:
        conn = get_connection()
        
        if params:
            df = pd.read_sql(query, conn, params=params)
        else:
            df = pd.read_sql(query, conn)
        
        return df
        
    except Exception as e:
        print(f"❌ Query execution failed: {e}")
        print(f"Query: {query}")
        raise
        
    finally:
        if conn:
            conn.close()


def insert_job_posting(job_data: Dict[str, Any]) -> Optional[int]:
    """
    Insert a job posting into staging.raw_jobs.
    
    Args:
        job_data: Dictionary with job posting fields
        
    Returns:
        job_id of inserted record, or None if duplicate
        
    Expected job_data keys:
        - job_title (required)
        - company (required)
        - location (optional)
        - job_description (required)
        - job_url (optional)
        - date_posted (optional)
        - salary_range (optional)
        - job_type (optional)
        - source (optional, defaults to 'manual')
    """
    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check for duplicate based on (company, job_title, date_posted)
        check_query = """
            SELECT job_id FROM staging.raw_jobs 
            WHERE company = ? AND job_title = ? AND date_posted = ?
        """
        cursor.execute(check_query, (
            job_data.get('company'),
            job_data.get('job_title'),
            job_data.get('date_posted')
        ))
        
        existing = cursor.fetchone()
        if existing:
            print(f"⚠️  Duplicate job found: {job_data.get('company')} - {job_data.get('job_title')}")
            return None
        
        # Insert new job
        insert_query = """
            INSERT INTO staging.raw_jobs (
                job_title, company, location, job_description, job_url,
                date_posted, salary_range, job_type, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(insert_query, (
            job_data.get('job_title'),
            job_data.get('company'),
            job_data.get('location'),
            job_data.get('job_description'),
            job_data.get('job_url'),
            job_data.get('date_posted'),
            job_data.get('salary_range'),
            job_data.get('job_type'),
            job_data.get('source', 'manual')
        ))
        
        # Get the inserted job_id
        cursor.execute("SELECT @@IDENTITY")
        job_id = cursor.fetchone()[0]
        
        conn.commit()
        print(f"✓ Inserted job_id {job_id}: {job_data.get('company')} - {job_data.get('job_title')}")
        
        return int(job_id)
        
    except pyodbc.Error as e:
        print(f"❌ Insert failed: {e}")
        if conn:
            conn.rollback()
        raise
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def insert_cleaned_job(job_id: int, cleaned_data: Dict[str, Any]) -> bool:
    """
    Insert cleaned/processed job data into staging.job_postings_clean.
    
    Args:
        job_id: Reference to staging.raw_jobs
        cleaned_data: Dictionary with cleaned job fields and NLP metadata
        
    Returns:
        True if successful, False otherwise
        
    Expected cleaned_data keys:
        - job_title_clean
        - company
        - location
        - description_clean
        - qualifications_required (JSON)
        - qualifications_bonus (JSON)
        - responsibilities (JSON)
        - summary (text)
        - extracted_skills (JSON)
        - entities (JSON)
        - action_verbs (JSON)
        - domain_tags (JSON)
        - job_url
        - date_posted
    """
    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if already exists
        cursor.execute("SELECT job_id FROM staging.job_postings_clean WHERE job_id = ?", (job_id,))
        if cursor.fetchone():
            print(f"⚠️  Cleaned job already exists for job_id {job_id}, skipping")
            return False
        
        insert_query = """
            INSERT INTO staging.job_postings_clean (
                job_id, job_title_clean, company, location, description_clean,
                qualifications_required, qualifications_bonus, responsibilities, summary,
                extracted_skills, entities, action_verbs, domain_tags,
                job_url, date_posted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # Convert lists/dicts to JSON strings
        cursor.execute(insert_query, (
            job_id,
            cleaned_data.get('job_title_clean'),
            cleaned_data.get('company'),
            cleaned_data.get('location'),
            cleaned_data.get('description_clean'),
            json.dumps(cleaned_data.get('qualifications_required', [])),
            json.dumps(cleaned_data.get('qualifications_bonus', [])),
            json.dumps(cleaned_data.get('responsibilities', [])),
            cleaned_data.get('summary'),
            json.dumps(cleaned_data.get('extracted_skills', [])),
            json.dumps(cleaned_data.get('entities', {})),
            json.dumps(cleaned_data.get('action_verbs', [])),
            json.dumps(cleaned_data.get('domain_tags', [])),
            cleaned_data.get('job_url'),
            cleaned_data.get('date_posted')
        ))
        
        conn.commit()
        print(f"✓ Inserted cleaned data for job_id {job_id}")
        return True
        
    except pyodbc.Error as e:
        print(f"❌ Insert cleaned job failed: {e}")
        if conn:
            conn.rollback()
        raise
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_unprocessed_jobs() -> pd.DataFrame:
    """
    Get all jobs from raw_jobs that haven't been processed yet.
    
    Returns:
        DataFrame with unprocessed jobs
    """
    query = """
        SELECT * FROM staging.raw_jobs 
        WHERE is_processed = 0
        ORDER BY date_ingested DESC
    """
    return execute_query_df(query)


def mark_job_processed(job_id: int) -> None:
    """
    Mark a job as processed in staging.raw_jobs.
    
    Args:
        job_id: ID of job to mark as processed
    """
    query = "UPDATE staging.raw_jobs SET is_processed = 1 WHERE job_id = ?"
    execute_query(query, (job_id,), fetch=False)
    print(f"✓ Marked job_id {job_id} as processed")


def get_job_count() -> Dict[str, int]:
    """
    Get counts of jobs in different states.
    
    Returns:
        Dictionary with counts: total, processed, unprocessed
    """
    query = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_processed = 1 THEN 1 ELSE 0 END) as processed,
            SUM(CASE WHEN is_processed = 0 THEN 1 ELSE 0 END) as unprocessed
        FROM staging.raw_jobs
    """
    result = execute_query(query)
    
    if result:
        row = result[0]
        return {
            'total': row[0],
            'processed': row[1],
            'unprocessed': row[2]
        }
    return {'total': 0, 'processed': 0, 'unprocessed': 0}


def clear_staging_tables() -> None:
    """
    Clear all staging tables (for testing/reset).
    WARNING: This deletes all data!
    """
    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Must delete in order due to foreign keys
        cursor.execute("DELETE FROM staging.job_postings_clean")
        cursor.execute("DELETE FROM staging.raw_jobs")
        
        conn.commit()
        print("✓ Staging tables cleared")
        
    except pyodbc.Error as e:
        print(f"❌ Clear tables failed: {e}")
        if conn:
            conn.rollback()
        raise
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def clear_results_tables() -> None:
    """
    Clear all results tables (for testing/reset).
    WARNING: This deletes all scoring data!
    """
    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM results.granular_scores")
        cursor.execute("DELETE FROM results.job_rankings")
        
        conn.commit()
        print("✓ Results tables cleared")
        
    except pyodbc.Error as e:
        print(f"❌ Clear results failed: {e}")
        if conn:
            conn.rollback()
        raise
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# =============================================
# Testing/Utility Functions
# =============================================

def test_connection() -> bool:
    """
    Test database connection and print status.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        
        print("✓ Database connection successful")
        print(f"  Server: {version[:50]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


if __name__ == "__main__":
    # Test the module when run directly
    print("Testing db_utils module...")
    print()
    
    # Test connection
    test_connection()
    print()
    
    # Get job counts
    counts = get_job_count()
    print(f"Job counts: {counts}")