-- 模型盲测批次：开测时锁定训练样本，预测与现场判读分别密封，揭晓后才回流训练。
CREATE TABLE IF NOT EXISTS blind_batches (
    code VARCHAR(24) PRIMARY KEY,
    title VARCHAR(120) NOT NULL,
    status VARCHAR(12) NOT NULL CHECK (status IN ('sealed','revealed')),
    locked_at VARCHAR(25) NOT NULL,
    locked_sample_count INT NOT NULL CHECK (locked_sample_count >= 0),
    locked_snapshot TEXT NOT NULL,
    opened_by VARCHAR(150) NOT NULL,
    revealed_at VARCHAR(25),
    trial_total INT NOT NULL DEFAULT 0 CHECK (trial_total >= 0),
    false_clear_count INT NOT NULL DEFAULT 0 CHECK (false_clear_count >= 0)
);

ALTER TABLE roll_trials
    ADD COLUMN blind_batch_code VARCHAR(24) NULL,
    ADD COLUMN blind_sample_count INT NULL CHECK (blind_sample_count IS NULL OR blind_sample_count >= 0),
    ADD CONSTRAINT fk_roll_trials_blind_batch
        FOREIGN KEY (blind_batch_code) REFERENCES blind_batches(code);
