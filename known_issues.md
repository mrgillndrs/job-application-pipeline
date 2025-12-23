# KNOWN ISSUES & FUTURE WORK

**Project:** Job Application Pipeline  
**Last Updated:** December 23, 2025  
**Version:** V2 (Preprocessing)

---

## 🔴 HIGH PRIORITY ISSUES

### Issue #1: Responsibility Misclassification in V2

**Status:** 🟡 Identified, Not Fixed  
**Severity:** High (affects Accenture and potentially other jobs)  
**Affected Module:** `src/preprocess_v2.py`

**Description:**  
When action-oriented items appear in the qualifications section header, V2 incorrectly classifies them as qualifications instead of responsibilities.

**Example (Job #8: Accenture):**
```
WHAT YOU WILL NEED:
- Design, build, and optimize scalable data pipelines
- Contribute to the architecture and implementation...
- Apply ETL/ELT best practices...
```

These describe duties (what you'll do) but are under a "What You Will Need" header, so v2 treats them as qualifications.

**Impact:**
- Accenture: 18 responsibilities → 0 (all misclassified as qualifications)
- Semantic embeddings may be less accurate
- Responsibility alignment scoring cannot work properly

**Root Cause:**
Content validation logic doesn't penalize imperative verbs strongly enough:
```python
# Current validation:
if text starts with "Design", "Build", etc.:
    score -= 0.2  # Too small a penalty
```

When validation score is positive, text gets classified by section header rather than content.

**Fix Options:**

**Option A: Trust Section Detection (Recommended)**
- If in Responsibilities section → It's a responsibility (ignore validation)
- If in Qualifications section → It's a qualification (ignore validation)  
- Use validation only for ambiguous cases
- **Pros:** Simple, respects job poster's intent
- **Cons:** Won't catch genuine misplacements

**Option B: Improve Validation Scoring**
- Increase penalty for imperative verbs at start: -0.2 → -0.5
- Add strong responsibility indicators:
  - Starts with action verb: -0.5
  - Contains "you will" + action: -0.4
- **Pros:** Can catch misplacements automatically
- **Cons:** More complex, may need tuning

**Option C: Manual Header Classification**
- Build a map of known ambiguous headers:
  - "What You Will Need" → Could be either
  - "What You'll Do" → Definitely responsibilities
- Use content validation only for ambiguous headers
- **Pros:** Handles edge cases explicitly
- **Cons:** Requires maintaining header database

**Recommendation:** Start with Option A, add Option C if we find systematic ambiguous headers.

**Action Items:**
- [ ] Decide on fix approach
- [ ] Implement fix in preprocess_v2.py
- [ ] Re-run comparison to validate
- [ ] Test on Accenture job specifically

**Related:** Issue #4 (Section Detection vs Content Validation)

---

### Issue #2: Make-A-Wish Responsibility Count Still High

**Status:** 🟡 Under Investigation  
**Severity:** Medium (parsing quality question)  
**Affected Module:** `src/preprocess_v2.py`

**Description:**  
V2 successfully extracts 13 qualifications for Make-A-Wish (vs 0 in v1), but still shows 28 responsibilities (same as v1).

**Questions:**
1. Are all 28 items actually valid responsibilities?
2. Are qualifications still mixed in despite extraction?
3. Should some items be filtered (company info, benefits, etc.)?
4. Is the section boundary detection cutting off too late?

**Impact:**
- Responsibility embeddings may be diluted
- Unclear if this affects ranking score
- May indicate section detection ending too late

**Action Items:**
- [ ] Manual review of all 28 responsibility items
- [ ] Classify each as: Valid / Qualification / Boilerplate / Company Info
- [ ] Check section boundary: Where does "Responsibilities" section actually end?
- [ ] Determine if issue is detection or validation

**Related:** Issue #5 (Summary Length Variability)

---

### Issue #3: Make-A-Wish Ranking Still Too Low

**Status:** 🔴 Critical (Business Impact)  
**Severity:** High  
**Affected Module:** `src/rank.py`, `src/preprocess_v2.py`

**Description:**  
With V1 parsing, Make-A-Wish ranked dead last (0.081 score) despite being a relevant Data & Reporting Analyst role requiring 7+ years experience with SQL, Python, Tableau, and Power BI.

**Why This Matters:**
- It's a local Calgary job (no relocation needed)
- Uses all the technologies in resume
- 7+ years experience (matches experience level)
- Contract role (12 months, good for flexibility)

**V1 Issues (Confirmed):**
- 0 qualifications extracted
- Requirements mixed into 28 responsibilities
- Semantic signal diluted by culture/benefits text

**V2 Improvements:**
- 13 qualifications now extracted ✅
- Sections properly detected ✅
- **Unknown:** Will this be enough to fix ranking?

**Action Items:**
- [ ] Complete manual labeling to validate v2 quality
- [ ] Reset database and reprocess with v2
- [ ] Re-rank jobs and check Make-A-Wish position
- [ ] **Success Criteria:** Make-A-Wish should rank in top 5
- [ ] If still low: Investigate scoring weights and embeddings

**Testing Plan:**
```bash
# Full V2 pipeline test
python scripts/reset_preprocessing.py
# Update pipeline.py to import preprocess_v2
python -m src.pipeline --skip-ingestion
# Check rankings CSV
```

**Related:** Issue #1 (if responsibilities still misclassified), Issue #2 (if 28 responsibilities is problematic)

---

## 🟡 MEDIUM PRIORITY ISSUES

### Issue #4: Section Detection vs Content Validation Conflict

**Status:** 🟡 Design Decision Needed  
**Severity:** Medium  
**Affected Module:** `src/preprocess_v2.py`

**Description:**  
V2 has two classification mechanisms that can conflict:
1. **Section detection:** Based on headers (e.g., "What You'll Do")
2. **Content validation:** Based on text patterns (e.g., imperative verbs)

**Current Behavior:**  
Content validation can override section detection.

**Problem:**  
If section detection is correct but content validation disagrees, we get misclassifications (see Issue #1: Accenture).

**Question:**  
Which should take priority?

**Arguments for Section Detection Priority:**
- Job posters know where they put requirements vs duties
- Headers are explicit signals
- Most parseable job postings have clear sections
- Simpler mental model

**Arguments for Content Validation Priority:**
- Catches genuine misplacements
- Some job posters do mix content
- More "intelligent" parsing
- Can handle edge cases

**Recommendation:**  
Trust section detection by default, use content validation as:
1. Tiebreaker when section is ambiguous
2. Warning flag (log low-confidence items)
3. Filter for obviously wrong classifications

**Action Items:**
- [ ] Decide on priority strategy
- [ ] Update validation to be advisory rather than decisive
- [ ] Add confidence scoring to parsed output
- [ ] Flag low-confidence items for manual review

---

### Issue #5: Summary Length Variability

**Status:** 🟡 Needs Review  
**Severity:** Low (quality question)  
**Affected Module:** `src/preprocess_v2.py` - `build_summary_improved()`

**Description:**  
Summary lengths vary inconsistently between v1 and v2:
- Make-A-Wish: 2119 → 2686 chars (+567, **increased**)
- Environmental 360: 3855 → 1065 chars (-2790, **decreased**)

**Expected Behavior:**  
Summary should consistently:
- **Include:** Company description, role context, team info
- **Exclude:** Application instructions, EEO statements, benefits lists

**Questions:**
1. Is Make-A-Wish summary including too much?
2. Is Environmental 360 summary excluding too much?
3. Are exclusion patterns working consistently?

**Action Items:**
- [ ] Review both summaries manually
- [ ] Check what content is in each
- [ ] Verify exclusion patterns are working:
   - Equal opportunity statements
   - Application instructions
   - Benefits lists
   - Compensation details
- [ ] Adjust patterns if needed

**Test Cases:**
```python
# Should be excluded:
"We are an equal opportunity employer..."
"To apply, please submit resume to..."
"Benefits include medical, dental, 401k..."

# Should be included:
"TechCorp is a leading provider of cloud solutions..."
"You'll work with a team of 5 data analysts..."
```

---

### Issue #6: Required vs Bonus Classification Accuracy

**Status:** 🟡 Needs Validation  
**Severity:** Medium  
**Affected Module:** `src/preprocess_v2.py` - `parse_qualifications_improved()`

**Description:**  
Environmental 360 reclassification:
- V1: 0 required, 11 bonus
- V2: 9 required, 2 bonus

**Question:**  
Is v2's classification more accurate, or is it being too aggressive in marking items as required?

**Current Logic:**
```python
# Default to "required"
classification = 'required'

# Check for bonus indicators
bonus_keywords = ['preferred', 'nice to have', 'bonus', 'plus', 'asset']
if any(keyword in bullet.lower() for keyword in bonus_keywords):
    classification = 'bonus'
```

**Problem:**  
If bullet doesn't explicitly say "preferred", it defaults to required even if it's under a "Nice to Have" header.

**Action Items:**
- [ ] Manual labeling will establish ground truth
- [ ] Check subsection detection (is it catching "Preferred" headers?)
- [ ] May need to use section context more than bullet text
- [ ] Calculate precision/recall for required vs bonus

---

## 🟢 LOW PRIORITY / FUTURE ENHANCEMENTS

### Enhancement #1: Nested Bullet Support

**Status:** 🔵 Not Implemented  
**Priority:** Low  
**Affected Module:** `src/preprocess_v2.py` - `extract_bullets_robust()`

**Description:**  
Current bullet extraction doesn't handle nested/sub-bullets:

```
• Build data pipelines
  - Design architecture
  - Implement ETL processes
  - Monitor performance
• Create dashboards
```

**Current Behavior:**  
Only top-level bullets extracted.

**Desired Behavior:**  
Extract hierarchical structure:
- "Build data pipelines" (with sub-items: architecture, ETL, monitoring)
- "Create dashboards"

**Impact:**  
Low - most job postings use flat bullet lists. Nested bullets are rare.

**Action Items:**
- [ ] Survey job postings to see how common nested bullets are
- [ ] If common: Implement nested extraction
- [ ] Consider flattening vs preserving hierarchy
- [ ] Update data model to support parent-child relationships

---

### Enhancement #2: Multi-Resume Support

**Status:** 🔵 Planned  
**Priority:** Medium (Future Phase)  
**Affected Module:** `src/config.py`, `src/vectorize.py`, `src/rank.py`

**Description:**  
Currently system uses single resume (matthew-gillanders-resume.json). Original design anticipated multiple resume versions.

**Use Cases:**
1. Tailor resume for different job types (analyst vs engineer vs manager)
2. Test which resume version ranks better
3. A/B testing of resume content changes

**Current State:**
- Config has `CURRENT_RESUME_VERSION` variable
- Database has `resume_version` column in rankings table
- But only one resume file used

**Action Items:**
- [ ] Create resume template format
- [ ] Build resume variation generator
- [ ] Update vectorization to handle multiple resumes
- [ ] Update ranking to test all resume versions
- [ ] Add resume comparison report

**Related:** Potential for automated resume customization based on job requirements.

---

### Enhancement #3: Scoring Weight Optimization

**Status:** 🔵 Not Started  
**Priority:** Medium (After V2 Validation)  
**Affected Module:** `src/config.py`, `src/rank.py`

**Description:**  
Current score weights are estimated:
```python
SCORE_WEIGHTS = {
    'overall_similarity': 0.40,
    'required_match': 0.30,
    'responsibility_alignment': 0.20,
    'bonus_match': 0.10
}
```

**Questions:**
1. Are these optimal?
2. Should required_match have more weight?
3. Does responsibility_alignment matter enough?

**Approach:**
1. Manually rank 10-20 jobs by "true fit"
2. Test different weight combinations
3. Find weights that best match manual rankings
4. Use grid search or optimization algorithm

**Action Items:**
- [ ] Wait for v2 validation first
- [ ] Create manual "ground truth" job rankings
- [ ] Build weight tuning script
- [ ] Test different weight combinations
- [ ] Validate with human judgment

---

### Enhancement #4: Expanded Test Dataset

**Status:** 🔵 Planned  
**Priority:** Medium  
**Affected Module:** N/A (Data collection)

**Description:**  
Current test set: 9 jobs from Indeed (Calgary, data analyst roles)

**Limitations:**
- Small sample size
- Limited to one location
- Limited to similar role types
- All from one source (Indeed)

**Future Dataset Goals:**
- 50-100 job postings
- Multiple locations (Calgary, Toronto, Vancouver, Remote)
- Multiple role types (analyst, engineer, manager, scientist)
- Multiple sources (Indeed, LinkedIn, company websites)
- Different formats (some with headers, some without)

**Action Items:**
- [ ] Define sampling strategy (stratified by role type, location, source)
- [ ] Collect jobs using JobSpy
- [ ] Manual labeling of diverse examples
- [ ] Test v2 parsing across all formats
- [ ] Identify format patterns not covered by current regex

---

### Enhancement #5: Real-time Parsing Confidence Scores

**Status:** 🔵 Not Implemented  
**Priority:** Low  
**Affected Module:** `src/preprocess_v2.py`

**Description:**  
V2 computes confidence scores internally but doesn't expose them in output.

**Current Behavior:**
```python
qual_obj = {
    'text': bullet,
    'skill_type': skill_type,
    'confidence': qual_confidence  # Computed but not used
}
```

**Desired Behavior:**
- Store confidence scores in database
- Flag low-confidence items for manual review
- Display confidence in results export
- Allow filtering by confidence threshold

**Use Cases:**
1. Quality assurance: Review low-confidence items
2. Debugging: Understand why item was classified incorrectly
3. Progressive enhancement: Focus manual labeling on low-confidence items
4. User feedback: Show confidence to users, let them flag errors

**Action Items:**
- [ ] Add confidence columns to database schema
- [ ] Update insert queries to include confidence
- [ ] Add confidence thresholds to config
- [ ] Create low-confidence report
- [ ] Consider manual review workflow

---

## 📊 VALIDATION & TESTING NEEDS

### Task #1: Manual Labeling (In Progress)

**Priority:** 🔴 Critical  
**Status:** 🟡 Planned, Not Started

**Description:**  
Manually label 3 representative jobs to create ground truth dataset.

**Jobs to Label:**
1. Job #1: Make-A-Wish (problem case)
2. Job #8: Accenture (ranked #1, but v2 issues)
3. Job #2: Environmental 360 (admin role, for variety)

**What to Label:**
- Section boundaries (line numbers)
- Qualification classification (required/bonus/misclassified)
- Responsibility classification (valid/misclassified)
- Boilerplate identification (exclude/keep)

**Output:**  
Structured format for each job showing:
- Correct section boundaries
- Correct classification of each bullet
- What should be excluded vs kept

**Next Steps:**
1. Export jobs with line numbers (`export_for_labeling.py`)
2. Review and label each job
3. Document findings in structured format
4. Use as ground truth for accuracy calculation

---

### Task #2: Calculate V2 Accuracy Metrics

**Priority:** 🟡 High  
**Status:** ⚪ Blocked (Waiting for manual labeling)

**Metrics to Calculate:**

**Section Detection:**
- Precision: % of v2 detected sections that are correct
- Recall: % of actual sections that v2 found
- F1 Score: Harmonic mean

**Qualification Classification:**
- Precision: % of v2 qualifications that are actually qualifications
- Recall: % of actual qualifications v2 found
- F1 Score

**Required vs Bonus Accuracy:**
- % correctly classified as required
- % correctly classified as bonus
- Confusion matrix

**Responsibility Classification:**
- Precision/Recall for responsibilities
- % misclassified as qualifications

**Success Criteria:**
- Section detection: >85%
- Qualification extraction: >80% precision, >75% recall
- Responsibility extraction: >75% precision, >70% recall

---

### Task #3: V2 End-to-End Scoring Test

**Priority:** 🔴 Critical  
**Status:** ⚪ Not Started (Blocked by manual labeling decision)

**Description:**  
Run full pipeline with v2 parsing to see if Make-A-Wish ranking improves.

**Steps:**
```bash
# 1. Reset database
python scripts/reset_preprocessing.py

# 2. Update pipeline to use v2
# Edit src/pipeline.py: from src.preprocess_v2 import preprocess_job

# 3. Run full pipeline
python -m src.pipeline --skip-ingestion

# 4. Check results
# Compare new rankings CSV to original v1 rankings
```

**Expected Outcomes:**

**Success Case:**
- Make-A-Wish moves from #9 (0.081) to top 5 (>0.60)
- Other rankings remain sensible
- Top 3 still make intuitive sense

**Failure Case:**
- Make-A-Wish still ranks low
- OR rankings become worse (less intuitive)
- Need to investigate scoring logic, not just parsing

**Decision Point:**
- If success: Merge v2 → v1, move to enhancement phase
- If failure: Investigate scoring weights, embeddings, validation logic

---

## 🔧 TECHNICAL DEBT

### Debt #1: V1 vs V2 Code Duplication

**Description:**  
preprocess.py and preprocess_v2.py share ~60% of code (text cleaning, NLP extraction).

**Impact:**
- Bug fixes need to be applied to both
- Maintenance overhead
- Confusion about which version to use

**Resolution Path:**
1. Validate v2 performance
2. Merge v2 improvements into v1
3. Archive v1 as backup
4. Delete v2 file
5. Update all imports

**Timeline:** After v2 validation complete

---

### Debt #2: Hardcoded Skill Keywords

**Location:** `src/preprocess.py` and `src/preprocess_v2.py`

**Issue:**
```python
tech_keywords = [
    'python', 'sql', 'r', 'java', ...  # ~40 keywords
]
```

**Problems:**
- Hardcoded list needs manual updates
- May miss emerging technologies
- Language/tool specific (won't generalize)

**Better Approaches:**
1. External skills database (JSON file)
2. spaCy's entity ruler with custom patterns
3. Pre-trained skill extraction model

**Priority:** Low (current approach works well enough)

---

### Debt #3: Configuration in Code

**Location:** `src/preprocess_v2.py` - `SECTION_PATTERNS`

**Issue:**  
Regex patterns hardcoded in module, should be in config.py

**Impact:**
- Changing patterns requires code edit
- Can't A/B test different patterns easily
- Not accessible to non-programmers

**Resolution:**
```python
# Move to config.py
SECTION_PATTERNS = {...}

# Or even better, external YAML:
# config/section_patterns.yaml
```

**Priority:** Low (only matters if patterns need frequent tuning)

---

## 📈 METRICS TO TRACK

### Parsing Quality Metrics

- **Section Detection Rate:** % of jobs with sections successfully detected
- **Qualification Extraction Rate:** Avg qualifications per job (v1: 1.3, v2: 7.2)
- **Responsibility Extraction Rate:** Avg responsibilities per job
- **Parsing Confidence:** Avg confidence score across all classifications

### Ranking Quality Metrics

- **Top Match Relevance:** Is #1 job actually a good fit? (subjective)
- **Score Distribution:** Are scores well-spread (0.1-0.9) or clustered?
- **Skill Match Correlation:** Does skill_match_count correlate with overall_score?
- **Ranking Stability:** Do rankings change significantly with small parsing tweaks?

### System Performance Metrics

- **Processing Speed:** Jobs/second for preprocessing
- **Vectorization Speed:** Embeddings/second
- **End-to-End Time:** Minutes from ingest to rankings
- **Database Size:** Growth rate of tables

---

## 🎯 SUCCESS CRITERIA SUMMARY

### Must Have (Before V2 Sign-off)

- [ ] Make-A-Wish ranks in top 5 (currently #9)
- [ ] Section detection accuracy >85%
- [ ] Qualification extraction precision >80%
- [ ] No systematic misclassifications (like Accenture responsibilities issue)
- [ ] Manual review of top 5 jobs: All make intuitive sense

### Nice to Have (Future Enhancements)

- [ ] Required vs bonus accuracy >80%
- [ ] Responsibility classification precision >75%
- [ ] Summary construction excludes boilerplate consistently
- [ ] Confidence scores exposed in output
- [ ] Multi-resume support implemented

### Stretch Goals (Research Phase)

- [ ] Automated resume optimization suggestions
- [ ] ML-based section detection (vs rule-based)
- [ ] Real-time job matching API
- [ ] Interactive ranking adjustment UI

---

**END OF KNOWN ISSUES DOCUMENT**
