import json

from infra.bootstrap import migrate, seed_demo


if __name__ == "__main__":
    migrate()
    print(json.dumps(seed_demo(), sort_keys=True, ensure_ascii=False, default=str))
