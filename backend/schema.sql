-- PostgreSQL Schema for O2AI Fax Automation
-- This schema replaces the SQLite database with PostgreSQL

-- Create database (run this separately as superuser if needed)
-- CREATE DATABASE o2ai_fax_automation;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL
);

-- Create indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- User sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    tenant_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for user_sessions table
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_tenant_id ON user_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);


-- Ground truth table
CREATE TABLE IF NOT EXISTS ground_truth (
    id SERIAL PRIMARY KEY,
    processing_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    filename VARCHAR(500) NOT NULL,
    ground_truth TEXT NOT NULL,
    ocr_text TEXT,
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for ground_truth table
CREATE INDEX IF NOT EXISTS idx_ground_truth_processing_id ON ground_truth(processing_id);
CREATE INDEX IF NOT EXISTS idx_ground_truth_tenant_id ON ground_truth(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ground_truth_metadata_json ON ground_truth USING GIN(metadata_json);

-- Create a function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for ground_truth table
CREATE TRIGGER update_ground_truth_updated_at BEFORE UPDATE ON ground_truth
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create trigger for user_sessions last_activity
CREATE OR REPLACE FUNCTION update_last_activity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_activity = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_sessions_last_activity BEFORE UPDATE ON user_sessions
FOR EACH ROW EXECUTE FUNCTION update_last_activity();
