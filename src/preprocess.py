"""
Job description preprocessing module.
Handles text cleaning, structured parsing, and NLP feature extraction.
"""

import re
import json
from typing import Dict, List, Any, Tuple, Optional
from bs4 import BeautifulSoup
import spacy
from collections import defaultdict

from src.config import (
    SPACY_MODEL, SECTION_HEADERS, OWNERSHIP_KEYWORDS, 
    FREQUENCY_KEYWORDS, SOFT_SKILLS
)
from src.db_utils import (
    get_unprocessed_jobs, insert_cleaned_job, 
    mark_job_processed, get_job_count
)

# Load spaCy model globally (only load once)
print("Loading spaCy model...")
nlp = spacy.load(SPACY_MODEL)
print(f"✓ spaCy model '{SPACY_MODEL}' loaded")


# =============================================
# TEXT CLEANING
# =============================================

def clean_html(text: str) -> str:
    """
    Remove HTML tags and decode HTML entities.
    
    Args:
        text: Raw text possibly containing HTML
        
    Returns:
        Cleaned text without HTML
    """
    if not text:
        return ""
    
    # Parse HTML and extract text
    soup = BeautifulSoup(text, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Get text and normalize whitespace
    text = soup.get_text()
    
    return text


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace: collapse multiple spaces, remove extra newlines.
    
    Args:
        text: Text with irregular whitespace
        
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""
    
    # Replace multiple newlines with double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text.strip()


def clean_text(text: str) -> str:
    """
    Full text cleaning pipeline.
    
    Args:
        text: Raw text
        
    Returns:
        Cleaned text
    """
    text = clean_html(text)
    text = normalize_whitespace(text)
    return text


# =============================================
# STRUCTURED PARSING
# =============================================

def detect_section_boundaries(text: str) -> Dict[str, Tuple[int, int]]:
    """
    Detect section boundaries in job description.
    
    Args:
        text: Cleaned job description text
        
    Returns:
        Dictionary mapping section names to (start_pos, end_pos) tuples
    """
    lines = text.split('\n')
    boundaries = {}
    
    # Track found sections
    found_sections = []
    
    for idx, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # Skip very short lines
        if len(line_lower) < 3:
            continue
        
        # Check for qualifications section
        if any(header in line_lower for header in SECTION_HEADERS['qualifications']):
            if 'qualifications' not in [s[0] for s in found_sections]:
                found_sections.append(('qualifications', idx))
        
        # Check for responsibilities section
        elif any(header in line_lower for header in SECTION_HEADERS['responsibilities']):
            if 'responsibilities' not in [s[0] for s in found_sections]:
                found_sections.append(('responsibilities', idx))
    
    # Convert line indices to character positions
    char_positions = []
    char_count = 0
    for line in lines:
        char_positions.append(char_count)
        char_count += len(line) + 1  # +1 for newline
    
    # Map sections to character boundaries
    for i, (section_name, line_idx) in enumerate(found_sections):
        start_pos = char_positions[line_idx]
        
        # End position is start of next section, or end of text
        if i + 1 < len(found_sections):
            end_pos = char_positions[found_sections[i + 1][1]]
        else:
            end_pos = len(text)
        
        boundaries[section_name] = (start_pos, end_pos)
    
    return boundaries


def extract_bullet_points(text: str) -> List[str]:
    """
    Extract bullet points from text section.
    
    Args:
        text: Text containing bullet points
        
    Returns:
        List of bullet point strings
    """
    bullets = []
    
    # Common bullet patterns
    bullet_patterns = [
        r'^\s*[•\-\*]\s+(.+)$',  # • - *
        r'^\s*\d+[\.\)]\s+(.+)$',  # 1. 1)
        r'^\s*[a-z][\.\)]\s+(.+)$',  # a. a)
    ]
    
    lines = text.split('\n')
    current_bullet = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if line starts with bullet
        is_bullet = False
        for pattern in bullet_patterns:
            match = re.match(pattern, line)
            if match:
                # Save previous bullet if exists
                if current_bullet:
                    bullets.append(current_bullet.strip())
                # Start new bullet
                current_bullet = match.group(1)
                is_bullet = True
                break
        
        # If not a bullet start, append to current bullet (continuation)
        if not is_bullet and current_bullet:
            current_bullet += ' ' + line
    
    # Add last bullet
    if current_bullet:
        bullets.append(current_bullet.strip())
    
    return bullets


def classify_qualification(qual_text: str, section_context: str = '') -> str:
    """
    Classify qualification as 'required' or 'bonus'.
    
    Args:
        qual_text: Qualification text
        section_context: Surrounding text for context
        
    Returns:
        'required' or 'bonus'
    """
    text_lower = (qual_text + ' ' + section_context).lower()
    
    # Check for bonus indicators
    bonus_keywords = ['preferred', 'nice to have', 'bonus', 'plus', 'asset', 'ideal']
    if any(keyword in text_lower for keyword in bonus_keywords):
        return 'bonus'
    
    # Check for required indicators
    required_keywords = ['required', 'must have', 'must', 'essential', 'mandatory']
    if any(keyword in text_lower for keyword in required_keywords):
        return 'required'
    
    # Default to required if unclear
    return 'required'


def classify_skill_type(skill_text: str) -> str:
    """
    Classify skill as 'Hard' or 'Soft'.
    
    Args:
        skill_text: Skill description text
        
    Returns:
        'Hard' or 'Soft'
    """
    text_lower = skill_text.lower()
    
    # Check for soft skill keywords
    if any(soft_skill in text_lower for soft_skill in SOFT_SKILLS):
        return 'Soft'
    
    # Default to hard skill
    return 'Hard'


def parse_qualifications(text: str, section_context: str = '') -> Dict[str, List[Dict]]:
    """
    Parse qualifications section into required and bonus items.
    
    Args:
        text: Qualifications section text
        section_context: Headers or surrounding text for context
        
    Returns:
        Dictionary with 'required' and 'bonus' lists
    """
    bullets = extract_bullet_points(text)
    
    qualifications = {
        'required': [],
        'bonus': []
    }
    
    for bullet in bullets:
        classification = classify_qualification(bullet, section_context)
        skill_type = classify_skill_type(bullet)
        
        qual_obj = {
            'text': bullet,
            'skill_type': skill_type
        }
        
        qualifications[classification].append(qual_obj)
    
    return qualifications


def extract_ownership_level(text: str) -> str:
    """
    Extract ownership level from responsibility text.
    
    Args:
        text: Responsibility text
        
    Returns:
        Ownership level: 'manage', 'lead', 'support', or 'assist'
    """
    text_lower = text.lower()
    
    # Check each ownership level in priority order
    for level in ['manage', 'lead', 'support', 'assist']:
        if any(keyword in text_lower for keyword in OWNERSHIP_KEYWORDS[level]):
            return level
    
    # Default to 'lead' if no match
    return 'lead'


def extract_frequency(text: str) -> str:
    """
    Extract frequency from responsibility text.
    
    Args:
        text: Responsibility text
        
    Returns:
        Frequency: 'daily', 'weekly', 'regularly', or 'ad-hoc'
    """
    text_lower = text.lower()
    
    # Check each frequency level
    for freq in ['daily', 'weekly', 'regularly', 'ad-hoc']:
        if any(keyword in text_lower for keyword in FREQUENCY_KEYWORDS[freq]):
            return freq
    
    # Default to 'regularly' if no match
    return 'regularly'


def extract_activity_type(text: str) -> str:
    """
    Categorize activity into domain type.
    
    Args:
        text: Activity/responsibility text
        
    Returns:
        Activity type category
    """
    text_lower = text.lower()
    
    # Domain keyword mapping
    domain_map = {
        'Data Engineering': ['pipeline', 'etl', 'elt', 'ingest', 'data warehouse', 'data lake', 'spark', 'airflow'],
        'Data Visualization': ['dashboard', 'visualization', 'power bi', 'tableau', 'report', 'visual'],
        'Analytics': ['analysis', 'analyze', 'metric', 'kpi', 'insight', 'trend', 'statistical'],
        'Data Science': ['machine learning', 'model', 'algorithm', 'prediction', 'ml', 'ai'],
        'Database Management': ['database', 'sql', 'query', 'optimization', 'schema', 'index'],
        'Data Governance': ['quality', 'governance', 'compliance', 'security', 'privacy', 'gdpr'],
    }
    
    # Check each domain
    for domain, keywords in domain_map.items():
        if any(keyword in text_lower for keyword in keywords):
            return domain
    
    # Default to general
    return 'General'


def parse_responsibilities(text: str) -> List[Dict]:
    """
    Parse responsibilities section.
    
    Args:
        text: Responsibilities section text
        
    Returns:
        List of responsibility objects
    """
    bullets = extract_bullet_points(text)
    
    responsibilities = []
    
    for bullet in bullets:
        resp_obj = {
            'activity': bullet,
            'ownership_level': extract_ownership_level(bullet),
            'frequency': extract_frequency(bullet),
            'activity_type': extract_activity_type(bullet)
        }
        responsibilities.append(resp_obj)
    
    return responsibilities


def parse_job_description(text: str) -> Dict[str, Any]:
    """
    Parse job description into structured sections.
    
    Args:
        text: Cleaned job description text
        
    Returns:
        Dictionary with parsed sections
    """
    # Detect section boundaries
    boundaries = detect_section_boundaries(text)
    
    parsed = {
        'qualifications_required': [],
        'qualifications_bonus': [],
        'responsibilities': [],
        'summary': ''
    }
    
    # Extract qualifications
    if 'qualifications' in boundaries:
        start, end = boundaries['qualifications']
        qual_text = text[start:end]
        quals = parse_qualifications(qual_text, qual_text[:200])  # Pass context
        parsed['qualifications_required'] = quals['required']
        parsed['qualifications_bonus'] = quals['bonus']
    
    # Extract responsibilities
    if 'responsibilities' in boundaries:
        start, end = boundaries['responsibilities']
        resp_text = text[start:end]
        parsed['responsibilities'] = parse_responsibilities(resp_text)
    
    # Summary is everything not in other sections
    summary_parts = []
    last_end = 0
    
    for section_name in ['qualifications', 'responsibilities']:
        if section_name in boundaries:
            start, end = boundaries[section_name]
            # Add text before this section
            if start > last_end:
                summary_parts.append(text[last_end:start])
            last_end = end
    
    # Add remaining text
    if last_end < len(text):
        summary_parts.append(text[last_end:])
    
    parsed['summary'] = '\n\n'.join(summary_parts).strip()
    
    return parsed


# =============================================
# NLP FEATURE EXTRACTION
# =============================================

def extract_skills(text: str) -> List[str]:
    """
    Extract skills and technologies using spaCy NER.
    
    Args:
        text: Text to extract skills from (original casing preserved)
        
    Returns:
        List of unique skills
    """
    doc = nlp(text)
    skills = set()
    
    # Technology keywords to look for
    tech_keywords = [
        'python', 'sql', 'r', 'java', 'javascript', 'c#', 'c++',
        'power bi', 'tableau', 'excel', 'looker', 'qlik',
        'azure', 'aws', 'gcp', 'cloud',
        'spark', 'hadoop', 'kafka', 'airflow',
        'pandas', 'numpy', 'scikit-learn', 'tensorflow', 'pytorch',
        'git', 'docker', 'kubernetes',
        'etl', 'elt', 'api', 'rest',
        'machine learning', 'deep learning', 'nlp', 'ai',
        'statistics', 'mathematics', 'modeling'
    ]
    
    text_lower = text.lower()
    
    # Extract technology keywords
    for keyword in tech_keywords:
        if keyword in text_lower:
            # Find actual casing in original text
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            matches = pattern.findall(text)
            if matches:
                skills.add(matches[0])
    
    # Extract entities that look like technologies
    for ent in doc.ents:
        if ent.label_ in ['PRODUCT', 'ORG', 'GPE']:
            # Check if it's technology-related
            if any(tech in ent.text.lower() for tech in ['sql', 'python', 'azure', 'aws', 'bi']):
                skills.add(ent.text)
    
    return sorted(list(skills))


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract named entities using spaCy.
    
    Args:
        text: Text to extract entities from
        
    Returns:
        Dictionary mapping entity types to lists of entities
    """
    doc = nlp(text)
    
    entities = defaultdict(list)
    
    for ent in doc.ents:
        if ent.label_ in ['ORG', 'PRODUCT', 'GPE', 'PERSON']:
            entities[ent.label_].append(ent.text)
    
    # Remove duplicates and return
    return {k: list(set(v)) for k, v in entities.items()}


def extract_action_verbs(text: str) -> List[str]:
    """
    Extract action verbs using spaCy POS tagging.
    
    Args:
        text: Text to extract verbs from
        
    Returns:
        List of unique action verbs
    """
    doc = nlp(text)
    
    verbs = set()
    
    for token in doc:
        # Look for verbs (not auxiliary/modal verbs)
        if token.pos_ == 'VERB' and token.dep_ not in ['aux', 'auxpass']:
            # Get lemma (base form)
            verbs.add(token.lemma_)
    
    return sorted(list(verbs))


def extract_domain_tags(text: str) -> List[str]:
    """
    Extract domain/category tags based on content.
    
    Args:
        text: Text to categorize
        
    Returns:
        List of domain tags
    """
    text_lower = text.lower()
    
    domains = []
    
    # Domain keyword mapping (reuse from activity_type)
    domain_map = {
        'Data Engineering': ['pipeline', 'etl', 'elt', 'ingest', 'data warehouse', 'data lake', 'spark', 'airflow'],
        'Data Visualization': ['dashboard', 'visualization', 'power bi', 'tableau', 'report', 'visual', 'bi'],
        'Analytics': ['analysis', 'analyze', 'metric', 'kpi', 'insight', 'trend', 'statistical'],
        'Data Science': ['machine learning', 'model', 'algorithm', 'prediction', 'ml', 'ai', 'deep learning'],
        'Database Management': ['database', 'sql', 'query', 'optimization', 'schema', 'index', 'rdbms'],
        'Data Governance': ['quality', 'governance', 'compliance', 'security', 'privacy', 'gdpr'],
        'Cloud Computing': ['azure', 'aws', 'gcp', 'cloud', 'saas', 'paas', 'iaas'],
        'Business Intelligence': ['bi', 'business intelligence', 'reporting', 'power bi', 'tableau', 'looker'],
    }
    
    for domain, keywords in domain_map.items():
        if any(keyword in text_lower for keyword in keywords):
            domains.append(domain)
    
    return sorted(list(set(domains)))


# =============================================
# MAIN PREPROCESSING PIPELINE
# =============================================

def preprocess_job(job_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full preprocessing pipeline for a single job.
    
    Args:
        job_row: Row from staging.raw_jobs
        
    Returns:
        Dictionary ready for staging.job_postings_clean
    """
    job_id = job_row['job_id']
    raw_description = job_row['job_description']
    
    print(f"\nProcessing job_id {job_id}: {job_row['company']} - {job_row['job_title']}")
    
    # Step 1: Clean text
    clean_desc = clean_text(raw_description)
    
    # Step 2: Parse into structured sections (BEFORE NLP, preserves casing)
    parsed_sections = parse_job_description(clean_desc)
    
    # Step 3: Extract NLP features (from full clean text, preserves casing)
    extracted_skills = extract_skills(clean_desc)
    entities = extract_entities(clean_desc)
    action_verbs = extract_action_verbs(clean_desc)
    domain_tags = extract_domain_tags(clean_desc)
    
    # Step 4: Build cleaned data object
    cleaned_data = {
        'job_title_clean': job_row['job_title'],
        'company': job_row['company'],
        'location': job_row['location'],
        'description_clean': clean_desc,
        'qualifications_required': parsed_sections['qualifications_required'],
        'qualifications_bonus': parsed_sections['qualifications_bonus'],
        'responsibilities': parsed_sections['responsibilities'],
        'summary': parsed_sections['summary'],
        'extracted_skills': extracted_skills,
        'entities': entities,
        'action_verbs': action_verbs,
        'domain_tags': domain_tags,
        'job_url': job_row['job_url'],
        'date_posted': job_row['date_posted']
    }
    
    print(f"  ✓ Extracted {len(extracted_skills)} skills, {len(domain_tags)} domain tags")
    print(f"  ✓ Found {len(parsed_sections['qualifications_required'])} required quals, "
          f"{len(parsed_sections['qualifications_bonus'])} bonus quals")
    print(f"  ✓ Found {len(parsed_sections['responsibilities'])} responsibilities")
    
    return cleaned_data


def process_all_jobs() -> Dict[str, int]:
    """
    Process all unprocessed jobs in the database.
    
    Returns:
        Dictionary with processing statistics
    """
    stats = {'processed': 0, 'errors': 0}
    
    # Get unprocessed jobs
    df_jobs = get_unprocessed_jobs()
    
    if df_jobs.empty:
        print("No unprocessed jobs found")
        return stats
    
    print(f"\nFound {len(df_jobs)} unprocessed job(s)")
    print("="*60)
    
    # Process each job
    for idx, row in df_jobs.iterrows():
        try:
            # Convert row to dict
            job_dict = row.to_dict()
            
            # Preprocess
            cleaned_data = preprocess_job(job_dict)
            
            # Insert into clean table
            success = insert_cleaned_job(job_dict['job_id'], cleaned_data)
            
            if success:
                # Mark as processed
                mark_job_processed(job_dict['job_id'])
                stats['processed'] += 1
            
        except Exception as e:
            print(f"  ❌ Error processing job_id {row['job_id']}: {e}")
            stats['errors'] += 1
    
    return stats


# =============================================
# CLI Interface
# =============================================

if __name__ == "__main__":
    print("="*60)
    print("JOB DESCRIPTION PREPROCESSING")
    print("="*60)
    
    # Show current state
    counts = get_job_count()
    print(f"\nCurrent state:")
    print(f"  Total jobs: {counts['total']}")
    print(f"  Processed: {counts['processed']}")
    print(f"  Unprocessed: {counts['unprocessed']}")
    
    if counts['unprocessed'] == 0:
        print("\n✓ All jobs already processed!")
    else:
        # Process jobs
        stats = process_all_jobs()
        
        print("\n" + "="*60)
        print("PREPROCESSING SUMMARY")
        print("="*60)
        print(f"Jobs processed: {stats['processed']}")
        print(f"Errors: {stats['errors']}")
        
        # Show updated state
        counts = get_job_count()
        print(f"\nFinal state:")
        print(f"  Total jobs: {counts['total']}")
        print(f"  Processed: {counts['processed']}")
        print(f"  Unprocessed: {counts['unprocessed']}")
        
        print("\n✓ Preprocessing complete!")