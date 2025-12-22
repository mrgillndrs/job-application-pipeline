-- =============================================
-- Job Match Pipeline - Database Creation Script
-- =============================================

USE master;
GO

-- Drop database if exists (for clean testing)
IF EXISTS (SELECT name FROM sys.databases WHERE name = 'JobMatchPipeline')
BEGIN
    ALTER DATABASE JobMatchPipeline SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE JobMatchPipeline;
END
GO

-- Create database
CREATE DATABASE JobMatchPipeline;
GO

USE JobMatchPipeline;
GO

-- =============================================
-- Create Schemas
-- =============================================

CREATE SCHEMA staging;
GO

CREATE SCHEMA results;
GO

-- =============================================
-- STAGING TABLES
-- =============================================

-- Raw job postings (as ingested from JSON)
CREATE TABLE staging.raw_jobs (
    job_id INT IDENTITY(1,1) PRIMARY KEY,
    job_title NVARCHAR(500) NOT NULL,
    company NVARCHAR(500) NOT NULL,
    location NVARCHAR(500),
    job_description NVARCHAR(MAX) NOT NULL,
    job_url NVARCHAR(1000),
    date_posted DATE,
    salary_range NVARCHAR(200),
    job_type NVARCHAR(100),
    date_ingested DATETIME DEFAULT GETDATE(),
    source NVARCHAR(100), -- 'jobspy' or 'manual'
    is_processed BIT DEFAULT 0,
    CONSTRAINT unique_job UNIQUE (company, job_title, date_posted)
);
GO

-- Cleaned jobs with NLP metadata and structured parsing
CREATE TABLE staging.job_postings_clean (
    job_id INT PRIMARY KEY,
    job_title_clean NVARCHAR(500),
    company NVARCHAR(500),
    location NVARCHAR(500),
    description_clean NVARCHAR(MAX),
    
    -- Structured job description sections
    qualifications_required NVARCHAR(MAX),  -- JSON array: [{text, skill_type}]
    qualifications_bonus NVARCHAR(MAX),     -- JSON array: [{text, skill_type}]
    responsibilities NVARCHAR(MAX),         -- JSON array: [{activity, ownership_level, frequency, activity_type}]
    summary NVARCHAR(MAX),                  -- Plain text: remaining context
    
    -- NLP metadata (extracted from full description)
    extracted_skills NVARCHAR(MAX),  -- JSON array
    entities NVARCHAR(MAX),          -- JSON object
    action_verbs NVARCHAR(MAX),      -- JSON array
    domain_tags NVARCHAR(MAX),       -- JSON array
    
    job_url NVARCHAR(1000),
    date_posted DATE,
    
    FOREIGN KEY (job_id) REFERENCES staging.raw_jobs(job_id)
);
GO

-- =============================================
-- RESULTS TABLES
-- =============================================

-- Overall job rankings
CREATE TABLE results.job_rankings (
    ranking_id INT IDENTITY(1,1) PRIMARY KEY,
    job_id INT NOT NULL,
    resume_version VARCHAR(50) DEFAULT 'matthew-gillanders-resume',
    overall_score FLOAT,
    matched_skills NVARCHAR(MAX),    -- JSON array
    missing_skills NVARCHAR(MAX),    -- JSON array
    skill_match_count INT,
    skill_gap_count INT,
    ranked_date DATETIME DEFAULT GETDATE(),
    
    FOREIGN KEY (job_id) REFERENCES staging.raw_jobs(job_id)
);
GO

-- Granular content scores (resume bullets vs job)
CREATE TABLE results.granular_scores (
    score_id INT IDENTITY(1,1) PRIMARY KEY,
    job_id INT NOT NULL,
    resume_version VARCHAR(50),
    section_name NVARCHAR(100),      -- 'Projects', 'ProfessionalExperience', etc.
    subsection_name NVARCHAR(500),   -- 'Parks Canada Dashboard', etc.
    content_type NVARCHAR(50),       -- 'bullet', 'content', 'summary'
    content_text NVARCHAR(MAX),
    extracted_skills NVARCHAR(MAX),  -- JSON array
    entities NVARCHAR(MAX),          -- JSON object
    action_verbs NVARCHAR(MAX),      -- JSON array
    domain_tags NVARCHAR(MAX),       -- JSON array
    similarity_score FLOAT,
    scored_date DATETIME DEFAULT GETDATE(),
    
    FOREIGN KEY (job_id) REFERENCES staging.raw_jobs(job_id)
);
GO

-- =============================================
-- Indexes for Performance
-- =============================================

CREATE INDEX idx_job_rankings_score 
    ON results.job_rankings(overall_score DESC);
GO

CREATE INDEX idx_granular_job_section 
    ON results.granular_scores(job_id, section_name, similarity_score DESC);
GO

CREATE INDEX idx_raw_jobs_processed 
    ON staging.raw_jobs(is_processed);
GO

-- =============================================
-- Verification
-- =============================================

PRINT 'Database created successfully!';
PRINT '';
PRINT 'Schemas:';
SELECT name FROM sys.schemas WHERE name IN ('staging', 'results');
PRINT '';
PRINT 'Tables:';
SELECT 
    SCHEMA_NAME(schema_id) as [Schema],
    name as [Table]
FROM sys.tables
ORDER BY SCHEMA_NAME(schema_id), name;
GO