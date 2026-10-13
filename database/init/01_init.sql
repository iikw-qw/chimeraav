-- Chimera v5.0 Database Initialization
-- Все таблицы, индексы, партиции

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ═══════════════════════════════════════════
-- USERS
-- ═══════════════════════════════════════════
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    telegram_username VARCHAR(100),
    telegram_id BIGINT,
    telegram_verified BOOLEAN DEFAULT false,
    verification_code VARCHAR(6),
    app_version VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    onboarding_completed BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_telegram_id ON users(telegram_id);

-- ═══════════════════════════════════════════
-- DEVICES
-- ═══════════════════════════════════════════
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    device_type VARCHAR(10) NOT NULL CHECK (device_type IN ('android', 'ios')),
    serial_number VARCHAR(100) UNIQUE,
    ip_address INET,
    external_ip VARCHAR(45),
    vpn_active BOOLEAN DEFAULT false,
    proxy_info JSONB DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'busy', 'error', 'paused', 'calibrating')),
    battery_level SMALLINT,
    model VARCHAR(100),
    manufacturer VARCHAR(100),
    os_version VARCHAR(50),
    screen_resolution VARCHAR(20),
    ram_mb INTEGER,
    temperature REAL,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_devices_user_id ON devices(user_id);
CREATE INDEX idx_devices_status ON devices(status);
CREATE INDEX idx_devices_device_type ON devices(device_type);

-- ═══════════════════════════════════════════
-- SOCIAL ACCOUNTS
-- ═══════════════════════════════════════════
CREATE TABLE social_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    platform VARCHAR(20) NOT NULL CHECK (platform IN ('instagram', 'threads', 'telegram', 'facebook', 'reddit', 'tiktok', 'twitter', 'linkedin', 'vk', 'youtube')),
    username VARCHAR(255) NOT NULL,
    password_encrypted VARCHAR(512),
    display_name VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'warming', 'paused', 'banned', 'suspended', 'limited')),
    proxy_url VARCHAR(500),
    followers_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    posts_count INTEGER DEFAULT 0,
    warmup_enabled BOOLEAN DEFAULT false,
    login_status VARCHAR(20) DEFAULT 'logged_out' CHECK (login_status IN ('logged_in', 'logged_out', 'captcha', 'error')),
    last_activity_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(platform, username)
);

CREATE INDEX idx_social_accounts_user_id ON social_accounts(user_id);
CREATE INDEX idx_social_accounts_device_id ON social_accounts(device_id);
CREATE INDEX idx_social_accounts_platform ON social_accounts(platform);
CREATE INDEX idx_social_accounts_status ON social_accounts(status);

-- ═══════════════════════════════════════════
-- TASKS
-- ═══════════════════════════════════════════
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    account_id UUID REFERENCES social_accounts(id) ON DELETE SET NULL,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'running', 'completed', 'failed', 'retrying', 'dead', 'cancelled')),
    priority SMALLINT DEFAULT 5,
    payload JSONB DEFAULT '{}',
    result JSONB DEFAULT '{}',
    error_message TEXT,
    retry_count SMALLINT DEFAULT 0,
    max_retries SMALLINT DEFAULT 3,
    scheduled_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_device_id ON tasks(device_id);
CREATE INDEX idx_tasks_account_id ON tasks(account_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_task_type ON tasks(task_type);
CREATE INDEX idx_tasks_scheduled_pending ON tasks(scheduled_at) WHERE status = 'pending';

-- ═══════════════════════════════════════════
-- DATASETS
-- ═══════════════════════════════════════════
CREATE TABLE datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    photos JSONB DEFAULT '[]',
    total_photos INTEGER DEFAULT 0,
    usage_stats JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_datasets_user_id ON datasets(user_id);

-- ═══════════════════════════════════════════
-- POSTS
-- ═══════════════════════════════════════════
CREATE TABLE posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES social_accounts(id) ON DELETE SET NULL,
    dataset_id UUID REFERENCES datasets(id) ON DELETE SET NULL,
    photos JSONB DEFAULT '[]',
    caption TEXT,
    platform VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'publishing', 'published', 'failed')),
    scheduled_at TIMESTAMP WITH TIME ZONE,
    published_at TIMESTAMP WITH TIME ZONE,
    engagement JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_account_id ON posts(account_id);
CREATE INDEX idx_posts_dataset_id ON posts(dataset_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_scheduled_at ON posts(scheduled_at);

-- ═══════════════════════════════════════════
-- TRACKED COMMENTS
-- ═══════════════════════════════════════════
CREATE TABLE tracked_comments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES social_accounts(id) ON DELETE CASCADE,
    platform VARCHAR(20) NOT NULL,
    post_url TEXT,
    commenter_username VARCHAR(255),
    commenter_user_id VARCHAR(255),
    commenter_gender VARCHAR(10) CHECK (commenter_gender IN ('male', 'female', 'unknown')),
    commenter_country VARCHAR(100),
    commenter_analysis JSONB DEFAULT '{}',
    comment_text TEXT,
    response_status VARCHAR(20) DEFAULT 'pending' CHECK (response_status IN ('pending', 'scheduled', 'sent', 'skipped', 'failed')),
    response_text TEXT,
    response_style VARCHAR(20) CHECK (response_style IN ('intriguing', 'vulgar')),
    response_scheduled_at TIMESTAMP WITH TIME ZONE,
    response_sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tracked_comments_account_id ON tracked_comments(account_id);
CREATE INDEX idx_tracked_comments_platform ON tracked_comments(platform);
CREATE INDEX idx_tracked_comments_response_status ON tracked_comments(response_status);

-- ═══════════════════════════════════════════
-- ACTION LOGS (Partitioned by month)
-- ═══════════════════════════════════════════
CREATE TABLE action_logs (
    id BIGSERIAL,
    device_id UUID,
    account_id UUID,
    action_type VARCHAR(50) NOT NULL,
    details JSONB DEFAULT '{}',
    success BOOLEAN DEFAULT true,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Партиции на 30 дней вперёд
DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE);
    end_date DATE;
    partition_name TEXT;
BEGIN
    FOR i IN 0..5 LOOP
        end_date := start_date + INTERVAL '1 month';
        partition_name := 'action_logs_' || TO_CHAR(start_date, 'YYYY_MM');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF action_logs FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );

        start_date := end_date;
    END LOOP;
END $$;

CREATE INDEX idx_action_logs_device_id ON action_logs(device_id);
CREATE INDEX idx_action_logs_account_id ON action_logs(account_id);
CREATE INDEX idx_action_logs_action_type ON action_logs(action_type);
CREATE INDEX idx_action_logs_created_at ON action_logs(created_at);

-- ═══════════════════════════════════════════
-- SCHEDULER PLANS
-- ═══════════════════════════════════════════
CREATE TABLE scheduler_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    accounts JSONB DEFAULT '[]',
    dataset_id UUID REFERENCES datasets(id) ON DELETE SET NULL,
    frequency VARCHAR(50),
    posts_per_day INTEGER DEFAULT 1,
    start_date DATE,
    end_date DATE,
    caption_style VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
    last_run_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_scheduler_plans_user_id ON scheduler_plans(user_id);
CREATE INDEX idx_scheduler_plans_status ON scheduler_plans(status);
CREATE INDEX idx_scheduler_plans_dataset_id ON scheduler_plans(dataset_id);

-- ═══════════════════════════════════════════
-- APP SETTINGS
-- ═══════════════════════════════════════════
CREATE TABLE app_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    key VARCHAR(100) NOT NULL,
    value JSONB DEFAULT '{}',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, key)
);

CREATE INDEX idx_app_settings_user_id ON app_settings(user_id);
CREATE INDEX idx_app_settings_key ON app_settings(key);

-- ═══════════════════════════════════════════
-- NOTIFICATIONS
-- ═══════════════════════════════════════════
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    read BOOLEAN DEFAULT false,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_read ON notifications(read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);

-- ═══════════════════════════════════════════
-- ФУНКЦИЯ ОБНОВЛЕНИЯ updated_at
-- ═══════════════════════════════════════════
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_devices_updated_at BEFORE UPDATE ON devices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_social_accounts_updated_at BEFORE UPDATE ON social_accounts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_app_settings_updated_at BEFORE UPDATE ON app_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
