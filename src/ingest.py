"""
Job posting ingestion module.
Loads job postings from JSON files into staging.raw_jobs table.
Handles both JobSpy output format and manual JSON format.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

from src.config import RAW_DATA_DIR
from src.db_utils import insert_job_posting, get_job_count


def load_json_file(filepath: Path) -> List[Dict[str, Any]]:
    """
    Load and parse a JSON file containing job postings.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        List of job posting dictionaries
        
    Raises:
        ValueError: If JSON is invalid or not a list
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both list format and single object format
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            raise ValueError(f"JSON must be a list or dict, got {type(data)}")
        
        print(f"✓ Loaded {len(data)} job(s) from {filepath.name}")
        return data
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {filepath.name}: {e}")
        raise
    except Exception as e:
        print(f"❌ Error reading {filepath.name}: {e}")
        raise


def normalize_job_data(raw_job: Dict[str, Any], source: str = 'manual') -> Dict[str, Any]:
    """
    Normalize job posting data to match database schema.
    Handles variations in field names from different sources.
    
    Args:
        raw_job: Raw job dictionary from JSON
        source: Data source ('jobspy' or 'manual')
        
    Returns:
        Normalized job dictionary ready for database insert
    """
    # Map various field name variations to our schema
    normalized = {
        'job_title': (
            raw_job.get('job_title') or 
            raw_job.get('title') or 
            raw_job.get('position') or
            'Unknown Title'
        ),
        'company': (
            raw_job.get('company') or 
            raw_job.get('company_name') or
            'Unknown Company'
        ),
        'location': (
            raw_job.get('location') or 
            raw_job.get('job_location') or
            None
        ),
        'job_description': (
            raw_job.get('job_description') or 
            raw_job.get('description') or 
            raw_job.get('job_details') or
            ''
        ),
        'job_url': (
            raw_job.get('job_url') or 
            raw_job.get('url') or 
            raw_job.get('link') or
            None
        ),
        'salary_range': (
            raw_job.get('salary_range') or 
            raw_job.get('salary') or
            None
        ),
        'job_type': (
            raw_job.get('job_type') or 
            raw_job.get('employment_type') or
            None
        ),
        'source': source
    }
    
    # Handle date_posted - try multiple formats
    date_posted = raw_job.get('date_posted') or raw_job.get('posted_date')
    if date_posted:
        try:
            # Check if it's a Unix timestamp (number)
            if isinstance(date_posted, (int, float)):
                # Convert milliseconds to seconds and then to date
                normalized['date_posted'] = datetime.fromtimestamp(date_posted / 1000).date()
            # Try parsing as ISO format string
            elif isinstance(date_posted, str):
                normalized['date_posted'] = datetime.fromisoformat(date_posted.replace('Z', '+00:00')).date()
            else:
                normalized['date_posted'] = date_posted
        except (ValueError, AttributeError, OSError) as e:
            print(f"  ⚠️  Could not parse date '{date_posted}', using today's date")
            normalized['date_posted'] = datetime.now().date()
    else:
        # Default to today if no date provided
        normalized['date_posted'] = datetime.now().date()
    
    # Validate required fields
    if not normalized['job_description']:
        raise ValueError(f"Job description is required: {raw_job.get('job_title', 'Unknown')}")
    
    return normalized


def ingest_json_file(filepath: Path, source: str = 'manual') -> Dict[str, int]:
    """
    Ingest a single JSON file into the database.
    
    Args:
        filepath: Path to JSON file
        source: Data source identifier ('jobspy' or 'manual')
        
    Returns:
        Dictionary with counts: {'inserted': int, 'duplicates': int, 'errors': int}
    """
    stats = {'inserted': 0, 'duplicates': 0, 'errors': 0}
    
    try:
        # Load jobs from file
        raw_jobs = load_json_file(filepath)
        
        # Process each job
        for idx, raw_job in enumerate(raw_jobs, 1):
            try:
                # Normalize the data
                normalized_job = normalize_job_data(raw_job, source)
                
                # Insert into database
                job_id = insert_job_posting(normalized_job)
                
                if job_id:
                    stats['inserted'] += 1
                else:
                    stats['duplicates'] += 1
                    
            except Exception as e:
                print(f"❌ Error processing job {idx} in {filepath.name}: {e}")
                stats['errors'] += 1
        
        print(f"\n✓ File {filepath.name} processed:")
        print(f"  - Inserted: {stats['inserted']}")
        print(f"  - Duplicates: {stats['duplicates']}")
        print(f"  - Errors: {stats['errors']}")
        
        return stats
        
    except Exception as e:
        print(f"❌ Failed to process file {filepath.name}: {e}")
        stats['errors'] = len(raw_jobs) if 'raw_jobs' in locals() else 1
        return stats


def ingest_all_json_files(source: str = 'manual') -> Dict[str, int]:
    """
    Ingest all JSON files from data/raw/ directory.
    
    Args:
        source: Data source identifier ('jobspy' or 'manual')
        
    Returns:
        Dictionary with total counts across all files
    """
    print(f"Looking for JSON files in: {RAW_DATA_DIR}")
    print()
    
    # Find all JSON files
    json_files = list(RAW_DATA_DIR.glob('*.json'))
    
    if not json_files:
        print("⚠️  No JSON files found in data/raw/")
        return {'inserted': 0, 'duplicates': 0, 'errors': 0}
    
    print(f"Found {len(json_files)} JSON file(s)")
    print()
    
    # Process each file
    total_stats = {'inserted': 0, 'duplicates': 0, 'errors': 0}
    
    for filepath in json_files:
        file_stats = ingest_json_file(filepath, source)
        
        # Aggregate stats
        for key in total_stats:
            total_stats[key] += file_stats[key]
    
    # Print summary
    print("\n" + "="*50)
    print("INGESTION SUMMARY")
    print("="*50)
    print(f"Files processed: {len(json_files)}")
    print(f"Jobs inserted: {total_stats['inserted']}")
    print(f"Duplicates skipped: {total_stats['duplicates']}")
    print(f"Errors: {total_stats['errors']}")
    
    # Show current database counts
    counts = get_job_count()
    print(f"\nTotal jobs in database: {counts['total']}")
    print(f"  - Processed: {counts['processed']}")
    print(f"  - Unprocessed: {counts['unprocessed']}")
    
    return total_stats


def create_sample_job_json(filepath: Optional[Path] = None) -> Path:
    """
    Create a sample job posting JSON file for testing.
    
    Args:
        filepath: Where to save the file (default: data/raw/sample_job.json)
        
    Returns:
        Path to created file
    """
    if filepath is None:
        filepath = RAW_DATA_DIR / 'sample_job.json'
    
    sample_jobs = [
        {
            "job_title": "Senior Data Analyst",
            "company": "Tech Corp Inc",
            "location": "Remote - Canada",
            "job_description": """
We are seeking a Senior Data Analyst to join our growing team.

Responsibilities:
- Develop and maintain Power BI dashboards
- Design and implement ETL pipelines
- Analyze business metrics and provide insights
- Collaborate with stakeholders across the organization

Requirements:
- 3+ years of experience with SQL and Python
- Strong experience with Power BI or similar BI tools
- Experience with cloud platforms (Azure preferred)
- Excellent communication skills

Nice to Have:
- Azure Data Engineer certification
- Experience with machine learning
- Knowledge of advanced statistical methods
            """,
            "job_url": "https://example.com/jobs/senior-data-analyst",
            "date_posted": "2025-12-20",
            "salary_range": "$80,000 - $110,000",
            "job_type": "Full-time"
        },
        {
            "job_title": "Data Engineer",
            "company": "Data Solutions Ltd",
            "location": "Toronto, ON",
            "job_description": """
Join our data engineering team to build scalable data pipelines.

What You'll Do:
- Build and maintain data pipelines using Python and SQL
- Work with Azure data services (Data Factory, Synapse)
- Optimize database performance
- Support data analysts and scientists

Required Qualifications:
- 2+ years in data engineering
- Strong Python and SQL skills
- Experience with cloud data platforms
- Understanding of data modeling

Preferred:
- Spark or Databricks experience
- Real-time data processing knowledge
            """,
            "job_url": "https://example.com/jobs/data-engineer",
            "date_posted": "2025-12-19",
            "salary_range": "$90,000 - $120,000",
            "job_type": "Full-time"
        }
    ]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(sample_jobs, f, indent=2)
    
    print(f"✓ Created sample job file: {filepath}")
    return filepath


# =============================================
# CLI Interface
# =============================================

if __name__ == "__main__":
    import sys
    
    print("="*50)
    print("JOB POSTING INGESTION")
    print("="*50)
    print()
    
    # Check if user wants to create sample data
    if len(sys.argv) > 1 and sys.argv[1] == '--create-sample':
        create_sample_job_json()
        print("\nRun again without --create-sample to ingest the file")
        sys.exit(0)
    
    # Check current database state
    print("Current database state:")
    counts = get_job_count()
    print(f"  Total jobs: {counts['total']}")
    print(f"  Processed: {counts['processed']}")
    print(f"  Unprocessed: {counts['unprocessed']}")
    print()
    
    # Run ingestion
    stats = ingest_all_json_files(source='manual')
    
    print("\n✓ Ingestion complete!")