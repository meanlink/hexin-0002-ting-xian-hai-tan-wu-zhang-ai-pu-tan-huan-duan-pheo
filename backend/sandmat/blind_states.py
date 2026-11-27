from enum import StrEnum


class BlindStatus(StrEnum):
    # 盲测进行中：现场判读与预测对日常推演密封，不参与拟合。
    SEALED = 'sealed'
    # 全组判读与预测齐备并统一揭晓，样本自此可进入日常训练。
    REVEALED = 'revealed'
