# Job Application Pipeline

Automated NLP-based job ranking system that matches job postings against resume content using semantic similarity.

## Features

- **Automated Job Ingestion:** Load job postings from JSON files
- **Structured Parsing:** Extract qualifications (required/bonus) and responsibilities
- **NLP Analysis:** Extract skills, entities, action verbs, and domain tags
- **Semantic Matching:** Generate embeddings and calculate similarity scores
- **Skill Gap Analysis:** Identify matched and missing skills
- **Database Storage:** Track all jobs and rankings in SQL Server
- **Export Results:** CSV and JSON outputs for easy review

## Prerequisites

- Python 3.9+
- SQL Server (local instance)
- Git (optional, for version control)

## Setup

### 1. Clone/Download Project
```bash
cd path/to/your/workspace
# If using Git:
git clone <repo-url>
cd job-application-pipeline

# Or simply download and extract the project folder
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 4. Configure Database

Create `.env` file in project root:
```bash
DB_SERVER=localhost
DB_DATABASE=JobMatchPipeline
DB_DRIVER=ODBC Driver 17 for SQL Server
```

### 5. Create Database

Run the database creation script in SQL Server Management Studio:
```bash
sqlcmd -S localhost -E -i scripts/create_database.sql
```

Or open `scripts/create_database.sql` in SSMS and execute.

### 6. Add Your Resume

Place your resume JSON file in `data/resume/` as `matthew-gillanders-resume.json`

(Update `src/config.py` if using a different filename)

## Usage

### Quick Start - Full Pipeline

Run the entire pipeline with one command:
```bash
python -m src.pipeline
```

This will:
1. Ingest job postings from `data/raw/*.json`
2. Preprocess and parse job descriptions
3. Generate semantic embeddings
4. Rank jobs against your resume
5. Export results to `data/results/`

### Step-by-Step Usage

Run individual modules:
```bash
# 1. Ingest jobs
python -m src.ingest

# 2. Preprocess (clean text + NLP + parsing)
python -m src.preprocess

# 3. Generate embeddings
python -m src.vectorize

# 4. Rank and score jobs
python -m src.rank
```

### Re-ranking After Resume Update

If you update your resume and want to re-rank existing jobs:
```bash
python -m src.pipeline --quick
```

This skips ingestion, preprocessing, and vectorization (fast!).

### Adding New Jobs

1. Place new JSON files in `data/raw/`
2. Run: `python -m src.pipeline`

The pipeline automatically detects and processes only new jobs.

### Resetting Processed Data

To reprocess all jobs (e.g., after changing parsing rules):
```bash
python scripts/reset_preprocessing.py
python -m src.pipeline --skip-ingestion
```

## Project Structure
```
job-application-pipeline/
├── data/
│   ├── raw/              # Input: Job posting JSON files
│   ├── processed/        # Enhanced JSON with NLP tags (unused currently)
│   ├── vectors/          # Parquet files with embeddings
│   ├── results/          # Output: Rankings (CSV/JSON)
│   └── resume/           # Input: Resume JSON
├── src/
│   ├── config.py         # Configuration settings
│   ├── db_utils.py       # Database helper functions
│   ├── ingest.py         # Job posting ingestion
│   ├── preprocess.py     # Text cleaning + NLP + parsing
│   ├── vectorize.py      # Embedding generation
│   ├── rank.py           # Similarity scoring and ranking
│   └── pipeline.py       # Main orchestrator
├── scripts/
│   ├── create_database.sql        # Database setup
│   └── reset_preprocessing.py     # Clean slate script
├── .env                  # Database credentials (not in git)
├── .gitignore
├── requirements.txt
└── README.md
```

## Output Files

After running the pipeline, check `data/results/`:

- **`job_rankings_YYYYMMDD_HHMMSS.csv`** - Summary rankings with scores
- **`job_rankings_detailed_YYYYMMDD_HHMMSS.json`** - Detailed scores with granular matches

## Configuration

Edit `src/config.py` to customize:

- Score weights (overall similarity vs. skill match)
- Parsing keywords (section headers, ownership levels)
- Export settings (CSV/JSON output)
- Resume file path
- Top N content per section

## Troubleshooting

**"Database connection failed"**
- Verify SQL Server is running
- Check credentials in `.env`
- Test connection: `python src/db_utils.py`

**"No JSON files found"**
- Add job posting files to `data/raw/`
- Ensure files are valid JSON format

**"Resume file not found"**
- Place resume in `data/resume/`
- Update `RESUME_FILE` in `src/config.py`

**"Module not found" errors**
- Activate virtual environment: `venv\Scripts\activate`
- Reinstall dependencies: `pip install -r requirements.txt`

## Development

**Testing individual modules:**
```bash
# Test database connection
python -m src.db_utils

# Test configuration
python -c "from src.config import validate_config; validate_config()"

# View current job counts
python -c "from src.db_utils import get_job_count; print(get_job_count())"
```

## Author

[Matt Gillanders]