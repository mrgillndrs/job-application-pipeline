"""
Central configuration module for Job Matching Pipeline.
All file paths, database settings, and model configs defined here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================
# PROJECT PATHS
# =============================================

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / 'data'
RAW_DATA_DIR = DATA_DIR / 'raw'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'
VECTORS_DIR = DATA_DIR / 'vectors'
RESULTS_DIR = DATA_DIR / 'results'
RESUME_DIR = DATA_DIR / 'resume'

# Ensure all directories exist
for directory in [RAW_DATA_DIR, PROCESSED_DATA_DIR, VECTORS_DIR, RESULTS_DIR, RESUME_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# =============================================
# DATABASE CONFIGURATION
# =============================================

DB_CONFIG = {
    'server': os.getenv('DB_SERVER', 'localhost'),
    'database': os.getenv('DB_DATABASE', 'JobMatchPipeline'),
    'driver': os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server'),
    'username': os.getenv('DB_USERNAME'),  # Optional, for SQL Auth
    'password': os.getenv('DB_PASSWORD'),  # Optional, for SQL Auth
}

# =============================================
# NLP MODEL CONFIGURATION
# =============================================

# spaCy model for NLP tasks (NER, POS tagging, etc.)
SPACY_MODEL = 'en_core_web_sm'

# HuggingFace sentence transformer for embeddings
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'

# =============================================
# RESUME CONFIGURATION
# =============================================

# Current resume version to use for matching
CURRENT_RESUME_VERSION = 'matthew-gillanders-resume'

# Resume file path
RESUME_FILE = RESUME_DIR / 'matthew-gillanders-resume.json'

# =============================================
# SCORING CONFIGURATION
# =============================================

# Minimum similarity score for "good fit" (informational only)
FIT_THRESHOLD = 0.70

# Composite score weights (must sum to 1.0)
SCORE_WEIGHTS = {
    'overall_similarity': 0.40,      # Job vs full resume
    'required_match': 0.30,          # Required qualifications match rate
    'responsibility_alignment': 0.20, # Job responsibilities vs resume experience
    'bonus_match': 0.10,             # Bonus qualifications match rate
}

# Top N resume content items to compare per section
TOP_N_CONFIG = {
    'Summary': 1,
    'TechnicalSkills': 1,
    'Projects': 3,
    'ProfessionalExperience': 3,
    'Education': 2,
    'Certifications': 1,
}

# =============================================
# DEDUPLICATION CONFIGURATION
# =============================================

# Fields to check for duplicate job postings
DUPLICATE_CHECK_FIELDS = ['company', 'job_title', 'date_posted']

# =============================================
# EXPORT SETTINGS
# =============================================

# Enable/disable different export formats
EXPORT_SUMMARY_CSV = True       # Export job rankings to CSV
EXPORT_GRANULAR_JSON = True     # Export detailed scores to JSON

# =============================================
# PARSING CONFIGURATION
# =============================================

# Section detection keywords for structured parsing
SECTION_HEADERS = {
    'qualifications': [
        'requirements', 'qualifications', 'required qualifications',
        'must have', 'required skills', 'minimum qualifications',
        'what you need', 'what we need', 'you have'
    ],
    'qualifications_required': [
        'required', 'must have', 'required qualifications',
        'minimum qualifications', 'essential'
    ],
    'qualifications_bonus': [
        'preferred', 'nice to have', 'bonus', 'plus',
        'preferred qualifications', 'nice-to-have', 'desired'
    ],
    'responsibilities': [
        'responsibilities', 'you will', 'duties', 'day-to-day',
        'what you\'ll do', 'the role', 'your role', 'daily tasks'
    ]
}

# Ownership level keywords (for responsibilities parsing)
OWNERSHIP_KEYWORDS = {
    'manage': ['manage', 'lead', 'drive', 'own', 'direct', 'oversee'],
    'lead': ['develop', 'build', 'create', 'design', 'implement', 'establish'],
    'support': ['support', 'assist', 'help', 'contribute', 'collaborate'],
    'assist': ['maintain', 'monitor', 'review', 'participate']
}

# Frequency keywords (for responsibilities parsing)
FREQUENCY_KEYWORDS = {
    'daily': ['daily', 'day-to-day', 'regularly', 'routine', 'ongoing'],
    'weekly': ['weekly', 'bi-weekly', 'biweekly'],
    'regularly': ['frequently', 'often', 'continuous'],
    'ad-hoc': ['ad-hoc', 'as needed', 'occasional', 'periodic', 'from time to time']
}

# Soft skill keywords (for qualification tagging)
SOFT_SKILLS = [
    'communication', 'leadership', 'teamwork', 'collaboration',
    'problem solving', 'critical thinking', 'analytical',
    'detail-oriented', 'organized', 'self-motivated',
    'interpersonal', 'presentation', 'written', 'verbal'
]

# =============================================
# UTILITY FUNCTIONS
# =============================================

def get_db_connection_string():
    """
    Build database connection string based on authentication type.
    
    Returns:
        str: pyodbc connection string
    """
    server = DB_CONFIG['server']
    database = DB_CONFIG['database']
    driver = DB_CONFIG['driver']
    username = DB_CONFIG['username']
    password = DB_CONFIG['password']
    
    if username and password:
        # SQL Server Authentication
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password}"
        )
    else:
        # Windows Authentication
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"Trusted_Connection=yes;"
        )
    
    return conn_str


def validate_config():
    """
    Validate that all critical configuration is present.
    
    Raises:
        ValueError: If critical config is missing
    """
    # Check resume file exists
    if not RESUME_FILE.exists():
        raise ValueError(f"Resume file not found: {RESUME_FILE}")
    
    # Check score weights sum to 1.0
    weight_sum = sum(SCORE_WEIGHTS.values())
    if not (0.99 <= weight_sum <= 1.01):  # Allow small floating point errors
        raise ValueError(f"SCORE_WEIGHTS must sum to 1.0, got {weight_sum}")
    
    print("✓ Configuration validated successfully")


# Run validation when module is imported
if __name__ != "__main__":
    # Only validate when imported, not when run directly
    pass  # We'll validate explicitly in pipeline.py