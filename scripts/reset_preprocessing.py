"""
Reset preprocessing script - clears processed data for fresh analysis.
Useful when you want to re-process jobs after changing parsing rules.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import PROCESSED_DATA_DIR, VECTORS_DIR, RESULTS_DIR
from src.db_utils import clear_staging_tables, clear_results_tables, get_job_count


def confirm_reset() -> bool:
    """
    Ask user to confirm reset action.
    
    Returns:
        True if confirmed, False otherwise
    """
    print("="*70)
    print("  RESET PREPROCESSING DATA")
    print("="*70)
    print("\nThis will DELETE:")
    print("  - All processed job data (staging.job_postings_clean)")
    print("  - All job rankings (results.job_rankings)")
    print("  - All granular scores (results.granular_scores)")
    print("  - All embedding files (data/vectors/)")
    print("  - All result exports (data/results/)")
    print("\nRaw job data (staging.raw_jobs) will be preserved.")
    print("\nYou will need to re-run:")
    print("  1. python -m src.preprocess")
    print("  2. python -m src.vectorize")
    print("  3. python -m src.rank")
    print("  OR: python -m src.pipeline --skip-ingestion")
    
    response = input("\nAre you sure you want to continue? (yes/no): ")
    return response.lower() in ['yes', 'y']


def delete_files_in_directory(directory: Path, pattern: str = "*") -> int:
    """
    Delete all files matching pattern in directory.
    
    Args:
        directory: Directory to clean
        pattern: File pattern to match (default: all files)
        
    Returns:
        Number of files deleted
    """
    if not directory.exists():
        return 0
    
    count = 0
    for file in directory.glob(pattern):
        if file.is_file():
            file.unlink()
            count += 1
    
    return count


def reset_preprocessing() -> None:
    """Execute the reset process."""
    print("\n" + "="*70)
    print("  EXECUTING RESET")
    print("="*70)
    
    # 1. Clear database tables
    print("\n1. Clearing database tables...")
    try:
        clear_staging_tables()
        clear_results_tables()
        print("  ✓ Database tables cleared")
    except Exception as e:
        print(f"  ❌ Error clearing database: {e}")
        return
    
    # 2. Delete vector files
    print("\n2. Deleting embedding files...")
    vector_count = delete_files_in_directory(VECTORS_DIR, "*.parquet")
    print(f"  ✓ Deleted {vector_count} embedding file(s)")
    
    # 3. Delete result files
    print("\n3. Deleting result files...")
    csv_count = delete_files_in_directory(RESULTS_DIR, "*.csv")
    json_count = delete_files_in_directory(RESULTS_DIR, "*.json")
    print(f"  ✓ Deleted {csv_count} CSV and {json_count} JSON file(s)")
    
    # 4. Show current state
    print("\n" + "="*70)
    print("  RESET COMPLETE")
    print("="*70)
    
    counts = get_job_count()
    print(f"\nCurrent state:")
    print(f"  Raw jobs: {counts['total']}")
    print(f"  Processed: {counts['processed']}")
    print(f"  Unprocessed: {counts['unprocessed']}")
    
    print("\n✓ Ready for fresh preprocessing!")
    print("\nNext steps:")
    print("  Option 1 (Full pipeline): python -m src.pipeline --skip-ingestion")
    print("  Option 2 (Step-by-step):")
    print("    1. python -m src.preprocess")
    print("    2. python -m src.vectorize")
    print("    3. python -m src.rank")


if __name__ == "__main__":
    print("\n")
    
    # Show help if requested
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        print("\nUsage: python scripts/reset_preprocessing.py")
        print("\nThis is a destructive operation - you will be asked to confirm.")
        sys.exit(0)
    
    # Confirm before proceeding
    if confirm_reset():
        reset_preprocessing()
        print("\n")
    else:
        print("\n❌ Reset cancelled")
        print("\n")