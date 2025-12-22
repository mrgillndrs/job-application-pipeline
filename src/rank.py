"""
Job ranking module - Calculate similarity scores and rank jobs.
Compares job embeddings against resume embeddings to find best matches.
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime

from src.config import (
    SCORE_WEIGHTS, FIT_THRESHOLD, CURRENT_RESUME_VERSION,
    RESULTS_DIR, EXPORT_SUMMARY_CSV, EXPORT_GRANULAR_JSON
)
from src.vectorize import load_embeddings
from src.db_utils import execute_query_df, get_connection


# =============================================
# SIMILARITY CALCULATIONS
# =============================================

def calculate_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Similarity score between 0 and 1
    """
    # Reshape for sklearn
    emb1 = np.array(embedding1).reshape(1, -1)
    emb2 = np.array(embedding2).reshape(1, -1)
    
    similarity = cosine_similarity(emb1, emb2)[0][0]
    
    # Ensure result is between 0 and 1
    return max(0.0, min(1.0, similarity))


def find_best_resume_matches(job_embedding: np.ndarray, 
                             df_resume: pd.DataFrame,
                             top_n: int = 5) -> List[Dict]:
    """
    Find top N best matching resume content for a job.
    
    Args:
        job_embedding: Job embedding vector
        df_resume: DataFrame with resume embeddings
        top_n: Number of top matches to return
        
    Returns:
        List of top matches with scores
    """
    matches = []
    
    for idx, row in df_resume.iterrows():
        resume_embedding = np.array(row['embedding'])
        similarity = calculate_similarity(job_embedding, resume_embedding)
        
        matches.append({
            'section': row['section'],
            'subsection': row.get('subsection'),
            'content_type': row['content_type'],
            'text': row['text'],
            'similarity': similarity
        })
    
    # Sort by similarity and return top N
    matches.sort(key=lambda x: x['similarity'], reverse=True)
    return matches[:top_n]


# =============================================
# SKILL MATCHING
# =============================================

def extract_skills_from_job(job_id: int) -> Tuple[List[str], List[str]]:
    """
    Extract skills from a processed job.
    
    Args:
        job_id: Job ID
        
    Returns:
        Tuple of (all_skills, required_skills)
    """
    query = f"""
        SELECT extracted_skills, qualifications_required
        FROM staging.job_postings_clean
        WHERE job_id = {job_id}
    """
    
    df = execute_query_df(query)
    
    if df.empty:
        return [], []
    
    row = df.iloc[0]
    
    # All extracted skills
    all_skills = json.loads(row['extracted_skills']) if row['extracted_skills'] else []
    
    # Required skills from qualifications
    quals_required = json.loads(row['qualifications_required']) if row['qualifications_required'] else []
    required_skills = [q['text'] for q in quals_required]
    
    return all_skills, required_skills


def extract_skills_from_resume(df_resume: pd.DataFrame) -> List[str]:
    """
    Extract all skills mentioned in resume.
    
    Args:
        df_resume: DataFrame with resume embeddings and text
        
    Returns:
        List of skills from resume
    """
    # Get the TechnicalSkills section
    tech_skills = df_resume[df_resume['section'] == 'TechnicalSkills']
    
    if tech_skills.empty:
        return []
    
    # Extract skills from technical skills text
    skills_text = tech_skills.iloc[0]['text'].lower()
    
    # Common skill keywords to extract
    skill_keywords = [
        'python', 'sql', 'r', 'java', 'javascript', 'c#',
        'power bi', 'tableau', 'excel', 'looker',
        'azure', 'aws', 'gcp',
        'spark', 'hadoop', 'airflow',
        'pandas', 'numpy', 'scikit-learn',
        'git', 'docker', 'kubernetes',
        'machine learning', 'deep learning', 'nlp',
        'etl', 'api', 'rest'
    ]
    
    found_skills = [skill for skill in skill_keywords if skill in skills_text]
    
    return found_skills


def calculate_skill_match(job_skills: List[str], 
                          resume_skills: List[str]) -> Tuple[List[str], List[str], float]:
    """
    Calculate skill overlap between job and resume.
    
    Args:
        job_skills: Skills from job posting
        resume_skills: Skills from resume
        
    Returns:
        Tuple of (matched_skills, missing_skills, match_ratio)
    """
    # Normalize to lowercase for comparison
    job_skills_lower = [s.lower() for s in job_skills]
    resume_skills_lower = [s.lower() for s in resume_skills]
    
    # Find matches
    matched = []
    for job_skill in job_skills:
        if job_skill.lower() in resume_skills_lower:
            matched.append(job_skill)
    
    # Find gaps
    missing = []
    for job_skill in job_skills:
        if job_skill.lower() not in resume_skills_lower:
            missing.append(job_skill)
    
    # Calculate match ratio
    match_ratio = len(matched) / len(job_skills) if job_skills else 0.0
    
    return matched, missing, match_ratio


# =============================================
# JOB SCORING
# =============================================

def score_job(job_id: int, 
              df_jobs: pd.DataFrame,
              df_resume: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate comprehensive score for a single job.
    
    Args:
        job_id: Job ID to score
        df_jobs: DataFrame with job embeddings
        df_resume: DataFrame with resume embeddings
        
    Returns:
        Dictionary with scoring results
    """
    # Get job embeddings
    job_embeddings = df_jobs[df_jobs['job_id'] == job_id]
    
    if job_embeddings.empty:
        return None
    
    # Get overall resume embedding
    overall_resume = df_resume[df_resume['section'] == 'overall_resume'].iloc[0]
    overall_resume_embedding = np.array(overall_resume['embedding'])
    
    # 1. Overall similarity (job full description vs overall resume)
    full_desc = job_embeddings[job_embeddings['section'] == 'full_description']
    
    if not full_desc.empty:
        job_full_embedding = np.array(full_desc.iloc[0]['embedding'])
        overall_similarity = calculate_similarity(job_full_embedding, overall_resume_embedding)
    else:
        overall_similarity = 0.0
    
    # 2. Find best matching resume content
    best_matches = find_best_resume_matches(job_full_embedding, df_resume, top_n=5)
    
    # 3. Skill matching
    job_skills, required_skills = extract_skills_from_job(job_id)
    resume_skills = extract_skills_from_resume(df_resume)
    
    matched_skills, missing_skills, skill_match_ratio = calculate_skill_match(
        job_skills, resume_skills
    )
    
    # 4. Calculate composite score
    # For now, use overall similarity as primary score
    # (We'll enhance this with structured scoring in future iterations)
    composite_score = overall_similarity
    
    # Prepare results
    results = {
        'job_id': job_id,
        'overall_similarity': overall_similarity,
        'skill_match_ratio': skill_match_ratio,
        'matched_skills': matched_skills,
        'missing_skills': missing_skills,
        'skill_match_count': len(matched_skills),
        'skill_gap_count': len(missing_skills),
        'composite_score': composite_score,
        'best_resume_matches': best_matches
    }
    
    return results


# =============================================
# BATCH SCORING
# =============================================

def score_all_jobs() -> pd.DataFrame:
    """
    Score all jobs against resume.
    
    Returns:
        DataFrame with job scores and rankings
    """
    print("\n" + "="*60)
    print("SCORING JOBS AGAINST RESUME")
    print("="*60)
    
    # Load embeddings
    df_jobs = load_embeddings('job_embeddings')
    df_resume = load_embeddings('resume_embeddings')
    
    # Get job metadata
    query = """
        SELECT 
            r.job_id,
            r.company,
            r.job_title,
            r.location,
            r.job_url,
            r.date_posted,
            c.job_title_clean
        FROM staging.raw_jobs r
        LEFT JOIN staging.job_postings_clean c ON r.job_id = c.job_id
        WHERE r.is_processed = 1
        ORDER BY r.job_id
    """
    df_metadata = execute_query_df(query)
    
    # Score each job
    scores = []
    
    print(f"\nScoring {len(df_metadata)} job(s)...\n")
    
    for idx, row in df_metadata.iterrows():
        job_id = row['job_id']
        print(f"Job {job_id}: {row['company']} - {row['job_title']}")
        
        score_result = score_job(job_id, df_jobs, df_resume)
        
        if score_result:
            # Combine metadata with scores
            score_result.update({
                'company': row['company'],
                'job_title': row['job_title'],
                'location': row['location'],
                'job_url': row['job_url'],
                'date_posted': row['date_posted']
            })
            
            scores.append(score_result)
            
            print(f"  Overall similarity: {score_result['overall_similarity']:.3f}")
            print(f"  Skill match: {score_result['skill_match_count']}/{score_result['skill_match_count'] + score_result['skill_gap_count']}")
            print(f"  Composite score: {score_result['composite_score']:.3f}")
    
    # Convert to DataFrame and rank
    df_scores = pd.DataFrame(scores)
    df_scores = df_scores.sort_values('composite_score', ascending=False).reset_index(drop=True)
    df_scores['rank'] = range(1, len(df_scores) + 1)
    
    return df_scores


# =============================================
# DATABASE STORAGE
# =============================================

def store_rankings(df_scores: pd.DataFrame) -> None:
    """
    Store job rankings in database.
    
    Args:
        df_scores: DataFrame with job scores
    """
    print("\n" + "="*60)
    print("STORING RANKINGS IN DATABASE")
    print("="*60)
    
    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Clear existing rankings for this resume version
        cursor.execute(
            "DELETE FROM results.job_rankings WHERE resume_version = ?",
            (CURRENT_RESUME_VERSION,)
        )
        
        # Insert new rankings
        insert_query = """
            INSERT INTO results.job_rankings (
                job_id, resume_version, overall_score,
                matched_skills, missing_skills,
                skill_match_count, skill_gap_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        for idx, row in df_scores.iterrows():
            cursor.execute(insert_query, (
                row['job_id'],
                CURRENT_RESUME_VERSION,
                row['composite_score'],
                json.dumps(row['matched_skills']),
                json.dumps(row['missing_skills']),
                row['skill_match_count'],
                row['skill_gap_count']
            ))
        
        conn.commit()
        print(f"\n✓ Stored {len(df_scores)} job rankings in database")
        
    except Exception as e:
        print(f"❌ Error storing rankings: {e}")
        if conn:
            conn.rollback()
        raise
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# =============================================
# EXPORT FUNCTIONS
# =============================================

def export_summary_csv(df_scores: pd.DataFrame) -> None:
    """
    Export summary rankings to CSV.
    
    Args:
        df_scores: DataFrame with job scores
    """
    if not EXPORT_SUMMARY_CSV:
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = RESULTS_DIR / f'job_rankings_{timestamp}.csv'
    
    # Select key columns for CSV
    df_export = df_scores[[
        'rank', 'composite_score', 'company', 'job_title', 'location',
        'overall_similarity', 'skill_match_count', 'skill_gap_count',
        'job_url', 'date_posted'
    ]].copy()
    
    df_export.to_csv(filename, index=False)
    print(f"✓ Exported summary CSV: {filename.name}")


def export_detailed_json(df_scores: pd.DataFrame) -> None:
    """
    Export detailed scores with granular matches to JSON.
    
    Args:
        df_scores: DataFrame with job scores
    """
    if not EXPORT_GRANULAR_JSON:
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = RESULTS_DIR / f'job_rankings_detailed_{timestamp}.json'
    
    # Convert DataFrame to dict, handling non-serializable types
    results = {
        'export_date': timestamp,
        'resume_version': CURRENT_RESUME_VERSION,
        'jobs': df_scores.to_dict('records')
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"✓ Exported detailed JSON: {filename.name}")


# =============================================
# MAIN PIPELINE
# =============================================

def rank_jobs() -> pd.DataFrame:
    """
    Complete job ranking pipeline.
    
    Returns:
        DataFrame with ranked jobs
    """
    # Score all jobs
    df_scores = score_all_jobs()
    
    # Store in database
    store_rankings(df_scores)
    
    # Export results
    print("\n" + "="*60)
    print("EXPORTING RESULTS")
    print("="*60)
    
    export_summary_csv(df_scores)
    export_detailed_json(df_scores)
    
    return df_scores


# =============================================
# CLI Interface
# =============================================

if __name__ == "__main__":
    print("="*60)
    print("JOB RANKING MODULE")
    print("="*60)
    
    # Run ranking
    df_scores = rank_jobs()
    
    # Display summary
    print("\n" + "="*60)
    print("TOP 5 JOB MATCHES")
    print("="*60)
    
    for idx, row in df_scores.head(5).iterrows():
        print(f"\n#{row['rank']}: {row['company']} - {row['job_title']}")
        print(f"  Score: {row['composite_score']:.3f}")
        print(f"  Location: {row['location']}")
        print(f"  Skills: {row['skill_match_count']} matched, {row['skill_gap_count']} missing")
        print(f"  URL: {row['job_url']}")
    
    print("\n" + "="*60)
    print("✓ RANKING COMPLETE!")
    print("="*60)