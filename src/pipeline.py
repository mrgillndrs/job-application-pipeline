"""
Main pipeline orchestrator - runs the complete job matching workflow.
Coordinates ingestion, preprocessing, vectorization, and ranking.
"""

import sys
from pathlib import Path
from datetime import datetime

from src.config import validate_config, RAW_DATA_DIR
from src.db_utils import get_job_count, test_connection
from src.ingest import ingest_all_json_files
from src.preprocess import process_all_jobs
from src.vectorize import vectorize_all
from src.rank import rank_jobs


def print_header(title: str) -> None:
    """Print formatted section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def check_prerequisites() -> bool:
    """
    Check if all prerequisites are met before running pipeline.
    
    Returns:
        True if ready to run, False otherwise
    """
    print_header("CHECKING PREREQUISITES")
    
    issues = []
    
    # 1. Check database connection
    print("\n1. Testing database connection...")
    if not test_connection():
        issues.append("Database connection failed")
    
    # 2. Check configuration
    print("\n2. Validating configuration...")
    try:
        validate_config()
    except Exception as e:
        issues.append(f"Configuration error: {e}")
    
    # 3. Check for job files
    print("\n3. Checking for job posting files...")
    json_files = list(RAW_DATA_DIR.glob('*.json'))
    if not json_files:
        print(f"  ⚠️  No JSON files found in {RAW_DATA_DIR}")
        print(f"  Add job posting JSON files to data/raw/ before running")
        issues.append("No job posting files found")
    else:
        print(f"  ✓ Found {len(json_files)} JSON file(s)")
    
    # Print summary
    if issues:
        print("\n❌ PREREQUISITES NOT MET:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("\n✅ All prerequisites met!")
        return True


def run_pipeline(skip_ingestion: bool = False, 
                skip_preprocessing: bool = False,
                skip_vectorization: bool = False) -> bool:
    """
    Run the complete job matching pipeline.
    
    Args:
        skip_ingestion: Skip job ingestion (use existing data)
        skip_preprocessing: Skip preprocessing (use existing clean data)
        skip_vectorization: Skip vectorization (use existing embeddings)
        
    Returns:
        True if successful, False otherwise
    """
    start_time = datetime.now()
    
    print_header("JOB MATCHING PIPELINE")
    print(f"\nStarted: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Pipeline aborted - fix prerequisites first")
        return False
    
    try:
        # STEP 1: INGESTION
        if not skip_ingestion:
            print_header("STEP 1/4: JOB INGESTION")
            ingest_all_json_files(source='jobspy')
        else:
            print_header("STEP 1/4: JOB INGESTION (SKIPPED)")
            counts = get_job_count()
            print(f"\nUsing existing jobs: {counts['total']} total")
        
        # STEP 2: PREPROCESSING
        if not skip_preprocessing:
            print_header("STEP 2/4: TEXT PREPROCESSING & NLP")
            process_all_jobs()
        else:
            print_header("STEP 2/4: PREPROCESSING (SKIPPED)")
            counts = get_job_count()
            print(f"\nUsing existing processed jobs: {counts['processed']}")
        
        # STEP 3: VECTORIZATION
        if not skip_vectorization:
            print_header("STEP 3/4: EMBEDDING GENERATION")
            vectorize_all()
        else:
            print_header("STEP 3/4: VECTORIZATION (SKIPPED)")
            print("\nUsing existing embeddings")
        
        # STEP 4: RANKING (always run)
        print_header("STEP 4/4: JOB RANKING & SCORING")
        df_scores = rank_jobs()
        
        # COMPLETION
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print_header("PIPELINE COMPLETE!")
        print(f"\nCompleted: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {duration:.1f} seconds")
        print(f"\nTotal jobs ranked: {len(df_scores)}")
        print(f"Top match: {df_scores.iloc[0]['company']} - {df_scores.iloc[0]['job_title']}")
        print(f"Top score: {df_scores.iloc[0]['composite_score']:.3f}")
        
        print("\n✓ Results saved to data/results/")
        print("✓ Check the CSV file for complete rankings")
        
        return True
        
    except Exception as e:
        print(f"\n❌ PIPELINE FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_usage():
    """Display usage instructions."""
    print("""
Usage: python -m src.pipeline [options]

Options:
  --help              Show this help message
  --skip-ingestion    Skip ingestion step (use existing jobs)
  --skip-preprocessing Skip preprocessing step (use existing clean data)
  --skip-vectorization Skip vectorization step (use existing embeddings)
  --quick             Skip all except ranking (fastest re-run)

Examples:
  python -m src.pipeline                    # Run full pipeline
  python -m src.pipeline --quick            # Re-rank existing data
  python -m src.pipeline --skip-ingestion   # Process & rank new resume only

Pipeline Steps:
  1. Ingestion      - Load job postings from JSON files
  2. Preprocessing  - Clean text, extract NLP features, parse structure
  3. Vectorization  - Generate semantic embeddings
  4. Ranking        - Score jobs against resume and export results
""")


if __name__ == "__main__":
    # Parse command line arguments
    args = sys.argv[1:]
    
    if '--help' in args or '-h' in args:
        show_usage()
        sys.exit(0)
    
    # Determine which steps to skip
    skip_ingestion = '--skip-ingestion' in args
    skip_preprocessing = '--skip-preprocessing' in args
    skip_vectorization = '--skip-vectorization' in args
    
    # Quick mode: skip everything except ranking
    if '--quick' in args:
        skip_ingestion = True
        skip_preprocessing = True
        skip_vectorization = True
    
    # Run pipeline
    success = run_pipeline(
        skip_ingestion=skip_ingestion,
        skip_preprocessing=skip_preprocessing,
        skip_vectorization=skip_vectorization
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)