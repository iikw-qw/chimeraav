-- Hardware-bound auth + user/account extensions

-- Extend users
ALTER TABLE users ADD COLUMN IF NOT EXISTS hardware_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS login_count INT DEFAULT 0;

-- Extend social_accounts
ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS email VARCHAR(200);
ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS email_password_encrypted TEXT;
ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS session_cookies TEXT;
ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS login_attempts INT DEFAULT 0;

-- Hardware licenses
CREATE TABLE IF NOT EXISTS hardware_licenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    hardware_id VARCHAR(255) NOT NULL UNIQUE,
    hostname VARCHAR(200),
    os_name VARCHAR(50),
    os_version VARCHAR(50),
    cpu_info VARCHAR(200),
    ram_gb INT,
    mac_address VARCHAR(50),
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- Host metrics
CREATE TABLE IF NOT EXISTS host_metrics (
    id BIGSERIAL PRIMARY KEY,
    hardware_id VARCHAR(255),
    cpu_percent REAL,
    ram_percent REAL,
    disk_percent REAL,
    network_sent_mb REAL,
    network_recv_mb REAL,
    uptime_seconds BIGINT,
    active_devices INT,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_hw ON host_metrics(hardware_id, recorded_at);
