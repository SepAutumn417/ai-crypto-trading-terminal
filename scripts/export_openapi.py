"""导出 FastAPI OpenAPI schema 到 JSON 文件，供 openapi-typescript 生成前端类型。

用法：
    python scripts/export_openapi.py [output_path]

默认输出到 apps/web/openapi.json
"""
import json
import sys
from pathlib import Path

# 将 apps/api/src 加入 path 以便 import app.main
api_src = Path(__file__).resolve().parent.parent / "apps" / "api" / "src"
sys.path.insert(0, str(api_src))

# 将各 package src 加入 path
root = Path(__file__).resolve().parent.parent
for pkg in ("exchange-adapter", "shared", "ai-evaluator", "config-versioning"):
    p = root / "packages" / pkg / "src"
    if p.exists():
        sys.path.insert(0, str(p))

from app.main import app  # noqa: E402


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "apps" / "web" / "openapi.json"
    schema = app.openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OpenAPI schema exported to {output} ({len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
