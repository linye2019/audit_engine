import argparse
import json
import os
import sqlite3

from .core.engine import MedicareAuditEngine
from .models.claim import ClaimEvent, ClaimLine


def main():
    parser = argparse.ArgumentParser(description="医保智能审核引擎 CLI")
    parser.add_argument("db", help="SQLite 数据库路径")
    parser.add_argument("--init", action="store_true", help="初始化数据库（执行 schema.sql）")
    parser.add_argument("--stats", action="store_true", help="查看数据库统计")
    parser.add_argument("--audit", help="审核结算数据 JSON 文件")
    parser.add_argument("--stage", default="post_audit",
                        choices=["pre_check", "end_check", "post_audit"],
                        help="审核阶段（默认: post_audit）")

    args = parser.parse_args()

    if args.init:
        schema_path = args.db.replace(".db", "_schema.sql") if args.db.endswith(".db") else "schema.sql"
        if not os.path.exists(schema_path):
            schema_path = "schema.sql"
        with open(schema_path, "r") as f:
            sql = f.read()
        conn = sqlite3.connect(args.db)
        conn.executescript(sql)
        conn.close()
        print(f"[OK] 数据库已初始化: {args.db}")
        return

    if args.stats:
        conn = sqlite3.connect(args.db)
        rows = conn.execute("SELECT * FROM v_catalog_stats").fetchall()
        for row in rows:
            print(f"  {row[0]:25s} {row[1]:>6d} 条")
        conn.close()
        return

    if args.audit:
        with open(args.audit, "r") as f:
            data = json.load(f)

        engine = MedicareAuditEngine(args.db)
        try:
            claim_data = data.get("claim_event", data)
            claim = ClaimEvent(**{k: v for k, v in claim_data.items()
                                  if k in ClaimEvent.__dataclass_fields__})

            lines_data = data.get("claim_lines", [])
            lines = [ClaimLine(**{k: v for k, v in ld.items()
                                 if k in ClaimLine.__dataclass_fields__})
                     for ld in lines_data]

            print(f"[INFO] 开始审核: setl_id={claim.setl_id}, "
                  f"med_type={claim.med_type}, "
                  f"lines={len(lines)}, stage={args.stage}")

            engine.save_claim(claim)
            engine.save_lines(lines)

            results = engine.audit_claim(claim, lines, stage=args.stage)
            engine.save_results(results)

            violations = [r for r in results if r.verdict != "pass"]
            warnings = [r for r in results if r.verdict == "warning"]
            violations_count = [r for r in results if r.verdict == "violation"]

            print(f"[结果] 共检查 {len(lines)} 行，触发规则 {len(results)} 条")
            print(f"       明确违规: {len(violations_count)} 条")
            print(f"       可疑提示: {len(warnings)} 条")

            for r in results:
                icon = "[!]" if r.verdict == "violation" else "[?]" if r.verdict == "warning" else "[OK]"
                print(f"  {icon} 柱{r.pillar} | 行{r.line_no} | {r.rule_code} | {r.reasoning}")

        finally:
            engine.close()
        return


if __name__ == "__main__":
    main()