-- Database Schema for Healthcare Platform Simulation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: patients
CREATE TABLE IF NOT EXISTS patients (
    id VARCHAR(64) PRIMARY KEY,
    mrn VARCHAR(64) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table: jobs
CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(64) PRIMARY KEY,
    patient_id VARCHAR(64) REFERENCES patients(id) ON DELETE SET NULL,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    payload JSONB,
    result JSONB,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table: audit_logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    source_service VARCHAR(100) NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_patient ON jobs(patient_id);
CREATE INDEX IF NOT EXISTS idx_patients_mrn ON patients(mrn);

-- Insert dummy seed patients for simulation
INSERT INTO patients (id, mrn, first_name, last_name, date_of_birth, gender)
VALUES 
    ('pat-001', 'MRN-1001', 'Alice', 'Smith', '1985-04-12', 'Female'),
    ('pat-002', 'MRN-1002', 'Bob', 'Jones', '1978-09-23', 'Male'),
    ('pat-003', 'MRN-1003', 'Charlie', 'Brown', '1992-11-05', 'Male')
ON CONFLICT (id) DO NOTHING;
