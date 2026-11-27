CREATE TABLE IF NOT EXISTS mat_segments (
    code VARCHAR(12) PRIMARY KEY,
    label VARCHAR(100) NOT NULL,
    from_node VARCHAR(24) NOT NULL,
    to_node VARCHAR(24) NOT NULL,
    length_m DECIMAL(5,1) NOT NULL CHECK (length_m > 0),
    priority VARCHAR(16) NOT NULL CHECK (priority IN ('access','rescue','both')),
    state VARCHAR(12) NOT NULL CHECK (state IN ('laid','standby')),
    CHECK (from_node <> to_node)
);

CREATE TABLE IF NOT EXISTS roll_trials (
    code VARCHAR(24) PRIMARY KEY,
    segment_code VARCHAR(12) NOT NULL,
    observed_at VARCHAR(25) NOT NULL,
    slope_pct DECIMAL(5,2) NOT NULL CHECK (slope_pct BETWEEN 0 AND 20),
    moisture_pct DECIMAL(5,2) NOT NULL CHECK (moisture_pct BETWEEN 0 AND 100),
    rut_mm DECIMAL(5,2) NOT NULL CHECK (rut_mm BETWEEN 0 AND 100),
    observed_result VARCHAR(12) CHECK (observed_result IN ('clear','stuck')),
    predicted_result VARCHAR(12) CHECK (predicted_result IN ('clear','stuck')),
    clear_probability DECIMAL(7,6) CHECK (clear_probability BETWEEN 0 AND 1),
    sample_count INT CHECK (sample_count >= 0),
    FOREIGN KEY (segment_code) REFERENCES mat_segments(code)
);

CREATE TABLE IF NOT EXISTS mat_orders (
    code VARCHAR(24) PRIMARY KEY,
    retire_code VARCHAR(12) NOT NULL,
    deploy_code VARCHAR(12) NOT NULL,
    trial_code VARCHAR(24) NOT NULL,
    tide_window VARCHAR(50) NOT NULL,
    remarks VARCHAR(220) NOT NULL,
    state VARCHAR(12) NOT NULL CHECK (state IN ('draft','approved','handed')),
    author_name VARCHAR(120) NOT NULL,
    signatory VARCHAR(120),
    signed_at VARCHAR(25),
    signed_access_path VARCHAR(180),
    signed_rescue_path VARCHAR(180),
    handed_to VARCHAR(120),
    handed_at VARCHAR(25),
    CHECK (retire_code <> deploy_code),
    FOREIGN KEY (retire_code) REFERENCES mat_segments(code),
    FOREIGN KEY (deploy_code) REFERENCES mat_segments(code),
    FOREIGN KEY (trial_code) REFERENCES roll_trials(code)
);
