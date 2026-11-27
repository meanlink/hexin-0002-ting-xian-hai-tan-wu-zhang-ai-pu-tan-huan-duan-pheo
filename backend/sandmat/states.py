from enum import StrEnum


class SegmentState(StrEnum):
    LAID = 'laid'
    STANDBY = 'standby'


class TrialResult(StrEnum):
    CLEAR = 'clear'
    STUCK = 'stuck'


class OrderState(StrEnum):
    DRAFT = 'draft'
    APPROVED = 'approved'
    HANDED = 'handed'


class RoutePriority(StrEnum):
    ACCESS = 'access'
    RESCUE = 'rescue'
    BOTH = 'both'
