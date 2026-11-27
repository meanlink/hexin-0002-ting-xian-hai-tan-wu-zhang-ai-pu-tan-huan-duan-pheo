"""Tingzhou training shift, scaled to the available demo mat footprint."""

SEGMENTS = (
    ('A1', '北坡入滩', 'ramp', 'hub', 13.0, 'access', 'laid'),
    ('B2', '木道接驳', 'hub', 'turn', 11.5, 'both', 'laid'),
    ('C3', '浪线回转', 'turn', 'lookout', 16.0, 'access', 'laid'),
    ('D4', '内侧替补', 'hub', 'turn', 12.0, 'both', 'standby'),
    ('R1', '救援旁线', 'rescue', 'hub', 9.0, 'rescue', 'laid'),
    ('R2', '岗亭备用', 'rescue', 'hub', 9.5, 'rescue', 'standby'),
)

TRAINING = (
    ('A1', 2.0, 14.2, 1.5, 'clear'),
    ('C3', 2.7, 21.0, 2.2, 'clear'),
    ('B2', 3.5, 28.0, 3.3, 'clear'),
    ('D4', 2.1, 18.0, 2.7, 'clear'),
    ('R1', 3.3, 17.4, 1.0, 'clear'),
    ('R2', 2.8, 25.0, 2.9, 'clear'),
    ('C3', 6.8, 65.0, 22.0, 'stuck'),
    ('B2', 7.2, 70.0, 14.0, 'stuck'),
    ('D4', 5.9, 76.0, 15.5, 'stuck'),
    ('R1', 7.4, 81.0, 19.7, 'stuck'),
    ('B2', 6.1, 71.0, 18.2, 'stuck'),
    ('C3', 8.1, 91.0, 30.0, 'stuck'),
)
