-- Create the users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_pw VARCHAR(255) NOT NULL, -- This matches the Python code
    phone VARCHAR(20) UNIQUE,
    is_verified INTEGER DEFAULT 0, -- This column is now explicitly added
    telegram_chat_id VARCHAR(255) UNIQUE,
    otp_secret VARCHAR(10), -- This matches the Python code (was otp_code)
    otp_expires TIMESTAMP WITH TIME ZONE -- This column is now explicitly added
);

-- Create the invoices table
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    s3_key VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL, -- PENDING, PROCESSED, FAILED
    extracted_data JSONB, -- Store JSON data from OCR/classification
    category VARCHAR(50), -- Added: Column for storing the classified category
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_telegram_chat_id ON users (telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_invoices_user_id ON invoices (user_id);
CREATE INDEX IF NOT EXISTS idx_invoices_s3_key ON invoices (s3_key);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices (status);
CREATE INDEX IF NOT EXISTS idx_invoices_category ON invoices (category);


---- Create the users table
--CREATE TABLE IF NOT EXISTS users (
--    id SERIAL PRIMARY KEY,
--    email VARCHAR(255) UNIQUE NOT NULL,
--    hashed_pw VARCHAR(255) NOT NULL,
--    phone VARCHAR(20) UNIQUE,
--    telegram_chat_id VARCHAR(255) UNIQUE,
--    otp_code VARCHAR(10),
--    otp_expires TIMESTAMP WITH TIME ZONE
--);
--
---- Create the invoices table
--CREATE TABLE IF NOT EXISTS invoices (
--    id SERIAL PRIMARY KEY,
--    user_id INTEGER NOT NULL REFERENCES users(id),
--    s3_key VARCHAR(255) UNIQUE NOT NULL,
--    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL, -- PENDING, PROCESSED, FAILED
--    extracted_data JSONB, -- Store JSON data from OCR/classification
--    category VARCHAR(50), -- Added: Column for storing the classified category
--    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
--);
--
---- Add indexes for performance
--CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
--CREATE INDEX IF NOT EXISTS idx_users_telegram_chat_id ON users (telegram_chat_id);
--CREATE INDEX IF NOT EXISTS idx_invoices_user_id ON invoices (user_id);
--CREATE INDEX IF NOT EXISTS idx_invoices_s3_key ON invoices (s3_key);
--CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices (status);
--CREATE INDEX IF NOT EXISTS idx_invoices_category ON invoices (category);
--
--
