"""
Vectorization module - Generate embeddings for jobs and resume content.
Uses sentence-transformers for semantic embeddings.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer

from src.config import (
    EMBEDDING_MODEL, RESUME_FILE, VECTORS_DIR,
    CURRENT_RESUME_VERSION
)
from src.db_utils import execute_query_df

# Load embedding model globally (only load once)
print(f"Loading embedding model: {EMBEDDING_MODEL}")
model = SentenceTransformer(EMBEDDING_MODEL)
print(f"✓ Model loaded: {model.get_sentence_embedding_dimension()}-dimensional embeddings")


# =============================================
# JOB EMBEDDINGS
# =============================================

def generate_job_embeddings() -> pd.DataFrame:
    """
    Generate embeddings for all processed jobs.
    Creates embeddings for:
    - Full job description
    - Qualifications section
    - Responsibilities section
    - Summary section
    
    Returns:
        DataFrame with job embeddings
    """
    print("\n" + "="*60)
    print("GENERATING JOB EMBEDDINGS")
    print("="*60)
    
    # Get all processed jobs
    query = """
        SELECT 
            job_id,
            job_title_clean,
            company,
            description_clean,
            qualifications_required,
            qualifications_bonus,
            responsibilities,
            summary
        FROM staging.job_postings_clean
    """
    
    df_jobs = execute_query_df(query)
    
    if df_jobs.empty:
        print("⚠️  No processed jobs found")
        return pd.DataFrame()
    
    print(f"\nGenerating embeddings for {len(df_jobs)} job(s)...")
    
    embeddings_data = []
    
    for idx, row in df_jobs.iterrows():
        job_id = row['job_id']
        print(f"\nJob {job_id}: {row['company']} - {row['job_title_clean']}")
        
        # 1. Full description embedding
        full_text = row['description_clean']
        if full_text:
            embedding = model.encode(full_text, show_progress_bar=False)
            embeddings_data.append({
                'job_id': job_id,
                'section': 'full_description',
                'subsection': None,
                'text': full_text[:500],  # Store truncated text for reference
                'embedding': embedding.tolist()
            })
            print(f"  ✓ Full description embedding")
        
        # 2. Qualifications embedding (combine required + bonus)
        quals_req = json.loads(row['qualifications_required']) if row['qualifications_required'] else []
        quals_bonus = json.loads(row['qualifications_bonus']) if row['qualifications_bonus'] else []
        
        if quals_req or quals_bonus:
            # Combine all qualification text
            qual_texts = [q['text'] for q in quals_req + quals_bonus]
            qual_combined = ' '.join(qual_texts)
            
            if qual_combined:
                embedding = model.encode(qual_combined, show_progress_bar=False)
                embeddings_data.append({
                    'job_id': job_id,
                    'section': 'qualifications',
                    'subsection': None,
                    'text': qual_combined[:500],
                    'embedding': embedding.tolist()
                })
                print(f"  ✓ Qualifications embedding ({len(quals_req)} required, {len(quals_bonus)} bonus)")
        
        # 3. Responsibilities embedding
        responsibilities = json.loads(row['responsibilities']) if row['responsibilities'] else []
        
        if responsibilities:
            # Combine all responsibility activities
            resp_texts = [r['activity'] for r in responsibilities]
            resp_combined = ' '.join(resp_texts)
            
            if resp_combined:
                embedding = model.encode(resp_combined, show_progress_bar=False)
                embeddings_data.append({
                    'job_id': job_id,
                    'section': 'responsibilities',
                    'subsection': None,
                    'text': resp_combined[:500],
                    'embedding': embedding.tolist()
                })
                print(f"  ✓ Responsibilities embedding ({len(responsibilities)} items)")
        
        # 4. Summary embedding
        summary = row['summary']
        if summary and len(summary.strip()) > 50:  # Only if substantial summary exists
            embedding = model.encode(summary, show_progress_bar=False)
            embeddings_data.append({
                'job_id': job_id,
                'section': 'summary',
                'subsection': None,
                'text': summary[:500],
                'embedding': embedding.tolist()
            })
            print(f"  ✓ Summary embedding")
    
    # Convert to DataFrame
    df_embeddings = pd.DataFrame(embeddings_data)
    
    print(f"\n✓ Generated {len(df_embeddings)} embeddings for {len(df_jobs)} jobs")
    
    return df_embeddings


# =============================================
# RESUME EMBEDDINGS
# =============================================

def load_resume() -> Dict[str, Any]:
    """
    Load resume JSON file.
    
    Returns:
        Resume dictionary
    """
    if not RESUME_FILE.exists():
        raise FileNotFoundError(f"Resume file not found: {RESUME_FILE}")
    
    with open(RESUME_FILE, 'r', encoding='utf-8') as f:
        resume = json.load(f)
    
    return resume


def generate_resume_embeddings() -> pd.DataFrame:
    """
    Generate embeddings for resume content.
    Creates embeddings for:
    - Overall resume
    - Each major section
    - Each bullet point within sections
    
    Returns:
        DataFrame with resume embeddings
    """
    print("\n" + "="*60)
    print("GENERATING RESUME EMBEDDINGS")
    print("="*60)
    
    resume = load_resume()
    embeddings_data = []
    
    # 1. Generate overall resume embedding
    print("\nGenerating overall resume embedding...")
    
    # Combine all text from resume
    all_text_parts = []
    
    for section_name, section_content in resume.items():
        if not isinstance(section_content, list):
            continue
        
        for item in section_content:
            # Add main content
            if 'Content' in item:
                all_text_parts.append(item['Content'])
            
            # Add subsection
            if 'Subsection' in item:
                all_text_parts.append(item['Subsection'])
            
            # Add bullets
            if 'Bullet' in item and isinstance(item['Bullet'], list):
                all_text_parts.extend(item['Bullet'])
    
    overall_text = ' '.join(all_text_parts)
    overall_embedding = model.encode(overall_text, show_progress_bar=False)
    
    embeddings_data.append({
        'resume_version': CURRENT_RESUME_VERSION,
        'section': 'overall_resume',
        'subsection': None,
        'content_type': 'full_resume',
        'text': overall_text[:500],
        'embedding': overall_embedding.tolist()
    })
    print(f"  ✓ Overall resume embedding")
    
    # 2. Generate section-level embeddings
    print("\nGenerating section embeddings...")
    
    for section_name, section_content in resume.items():
        if not isinstance(section_content, list):
            continue
        
        print(f"\n{section_name}:")
        
        for item_idx, item in enumerate(section_content):
            # Handle sections with just Content (Summary, TechnicalSkills)
            if 'Content' in item and 'Subsection' not in item:
                content = item['Content']
                embedding = model.encode(content, show_progress_bar=False)
                
                embeddings_data.append({
                    'resume_version': CURRENT_RESUME_VERSION,
                    'section': section_name,
                    'subsection': None,
                    'content_type': 'content',
                    'text': content[:500],
                    'embedding': embedding.tolist()
                })
                print(f"  ✓ Content embedding")
            
            # Handle sections with Subsection + Bullets (Projects, Experience, etc.)
            if 'Subsection' in item:
                subsection_name = item['Subsection']
                
                # Create embedding for subsection header + bullets combined
                subsection_parts = [subsection_name]
                
                if 'Bullet' in item and isinstance(item['Bullet'], list):
                    subsection_parts.extend(item['Bullet'])
                
                subsection_text = ' '.join(subsection_parts)
                embedding = model.encode(subsection_text, show_progress_bar=False)
                
                embeddings_data.append({
                    'resume_version': CURRENT_RESUME_VERSION,
                    'section': section_name,
                    'subsection': subsection_name,
                    'content_type': 'subsection',
                    'text': subsection_text[:500],
                    'embedding': embedding.tolist()
                })
                print(f"  ✓ {subsection_name[:50]}...")
                
                # Also create embeddings for individual bullets
                if 'Bullet' in item and isinstance(item['Bullet'], list):
                    for bullet_idx, bullet in enumerate(item['Bullet']):
                        embedding = model.encode(bullet, show_progress_bar=False)
                        
                        embeddings_data.append({
                            'resume_version': CURRENT_RESUME_VERSION,
                            'section': section_name,
                            'subsection': subsection_name,
                            'content_type': 'bullet',
                            'text': bullet[:500],
                            'embedding': embedding.tolist()
                        })
                    print(f"    ✓ {len(item['Bullet'])} bullet embeddings")
    
    # Convert to DataFrame
    df_embeddings = pd.DataFrame(embeddings_data)
    
    print(f"\n✓ Generated {len(df_embeddings)} resume embeddings")
    
    return df_embeddings


# =============================================
# SAVE/LOAD FUNCTIONS
# =============================================

def save_embeddings(df: pd.DataFrame, filename: str) -> Path:
    """
    Save embeddings DataFrame to parquet file.
    
    Args:
        df: DataFrame with embeddings
        filename: Output filename (without extension)
        
    Returns:
        Path to saved file
    """
    filepath = VECTORS_DIR / f"{filename}.parquet"
    df.to_parquet(filepath, index=False)
    print(f"\n✓ Saved embeddings to: {filepath}")
    return filepath


def load_embeddings(filename: str) -> pd.DataFrame:
    """
    Load embeddings from parquet file.
    
    Args:
        filename: Filename (without extension)
        
    Returns:
        DataFrame with embeddings
    """
    filepath = VECTORS_DIR / f"{filename}.parquet"
    
    if not filepath.exists():
        raise FileNotFoundError(f"Embeddings file not found: {filepath}")
    
    df = pd.read_parquet(filepath)
    print(f"✓ Loaded {len(df)} embeddings from: {filepath}")
    return df


# =============================================
# MAIN PIPELINE
# =============================================

def vectorize_all() -> Dict[str, Path]:
    """
    Generate all embeddings (jobs + resume) and save to files.
    
    Returns:
        Dictionary with paths to saved files
    """
    saved_files = {}
    
    # Generate job embeddings
    df_job_embeddings = generate_job_embeddings()
    if not df_job_embeddings.empty:
        saved_files['job_embeddings'] = save_embeddings(df_job_embeddings, 'job_embeddings')
    
    # Generate resume embeddings
    df_resume_embeddings = generate_resume_embeddings()
    if not df_resume_embeddings.empty:
        saved_files['resume_embeddings'] = save_embeddings(df_resume_embeddings, 'resume_embeddings')
    
    return saved_files


# =============================================
# CLI Interface
# =============================================

if __name__ == "__main__":
    print("="*60)
    print("VECTORIZATION MODULE")
    print("="*60)
    
    # Run vectorization
    saved_files = vectorize_all()
    
    print("\n" + "="*60)
    print("VECTORIZATION COMPLETE")
    print("="*60)
    
    for file_type, filepath in saved_files.items():
        print(f"✓ {file_type}: {filepath.name}")
    
    print("\n✓ All embeddings generated and saved!")