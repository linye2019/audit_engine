"""AI 智能体主动分析接口 — 影响分析、冲突检测、覆盖率分析"""

import os
import sys
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["AI 智能体"])


class AnalysisResponse(BaseModel):
    result: str
    data: dict = {}
    success: bool = True


def _run_analysis(module_path, function_name, **kwargs):
    """运行分析模块"""
    analysis_dir = os.path.join(os.path.dirname(__file__), "../../tools/audit-assistant/analysis")
    sys.path.insert(0, analysis_dir)
    
    try:
        module = __import__(module_path)
        if hasattr(module, function_name):
            return getattr(module, function_name)(**kwargs)
        raise RuntimeError(f"函数 {function_name} 不存在")
    finally:
        if analysis_dir in sys.path:
            sys.path.remove(analysis_dir)


@router.get("/api/v1/agent/impact", summary="规则变更影响分析")
def impact_analysis(save_snapshot: bool = False):
    """对比当前规则与历史快照，识别新增/修改/删除"""
    analysis_dir = os.path.join(os.path.dirname(__file__), "../../tools/audit-assistant/analysis")
    sys.path.insert(0, analysis_dir)
    
    try:
        import impact_analysis as ia
        
        conn = ia.get_conn()
        conn.row_factory = __import__('sqlite3').Row
        current = ia.fetch_all_rules(conn)
        conn.close()
        
        if save_snapshot:
            path = ia.save_snapshot(current)
            return AnalysisResponse(
                result=f"✅ 快照已保存: {os.path.basename(path)} ({len(current)} 条规则)",
                data={"snapshot_path": path, "total_rules": len(current)}
            )
        
        snapshot = ia.get_latest_snapshot()
        if not snapshot:
            path = ia.save_snapshot(current)
            return AnalysisResponse(
                result=f"⚠️ 没有历史快照，已保存当前规则为基线: {os.path.basename(path)}\n下次运行将对比变更。",
                data={"baseline_saved": True, "snapshot_path": path, "total_rules": len(current)}
            )
        
        diff = ia.compare_rules(snapshot["rules"], current)
        s = diff["stats"]
        
        result_lines = []
        result_lines.append(f"📊 规则变更影响分析报告")
        result_lines.append(f"原规则数: {s['old_total']}")
        result_lines.append(f"现规则数: {s['new_total']}")
        
        if s["added_count"] > 0:
            result_lines.append(f"➕ 新增: {s['added_count']} 条")
            for r in diff["added"][:5]:
                result_lines.append(f"  • {r['code']} ({r['name']}) [{r['pillar']}/{r['stage']}]")
            if len(diff["added"]) > 5:
                result_lines.append(f"  ... 还有 {len(diff['added']) - 5} 条")
        
        if s["removed_count"] > 0:
            result_lines.append(f"❌ 删除: {s['removed_count']} 条")
            for r in diff["removed"][:5]:
                result_lines.append(f"  • {r['code']} ({r['name']})")
            if len(diff["removed"]) > 5:
                result_lines.append(f"  ... 还有 {len(diff['removed']) - 5} 条")
        
        if s["modified_count"] > 0:
            result_lines.append(f"✏️ 修改: {s['modified_count']} 条")
            for r in diff["modified"][:5]:
                result_lines.append(f"  • {r['code']} ({r['name']}):")
                for k, v in r["changes"].items():
                    result_lines.append(f"    {k}: {v['old']} → {v['new']}")
            if len(diff["modified"]) > 5:
                result_lines.append(f"  ... 还有 {len(diff['modified']) - 5} 条")
        
        if s["added_count"] == 0 and s["removed_count"] == 0 and s["modified_count"] == 0:
            result_lines.append(f"✅ 规则无变更")
        
        return AnalysisResponse(
            result="\n".join(result_lines),
            data=diff
        )
    
    except Exception as e:
        raise HTTPException(500, f"分析失败: {str(e)}")
    finally:
        if analysis_dir in sys.path:
            sys.path.remove(analysis_dir)


@router.get("/api/v1/agent/conflicts", summary="规则冲突检测")
def conflict_detection(pillar: str = None):
    """检测规则冲突（性别互斥、阶段不一致、conditions重复）"""
    analysis_dir = os.path.join(os.path.dirname(__file__), "../../tools/audit-assistant/analysis")
    sys.path.insert(0, analysis_dir)
    
    try:
        import conflict_detector as cd
        
        conn = cd.get_conn()
        conflicts = cd.detect_all(conn, pillar)
        conn.close()
        
        result_lines = []
        title = f"规则冲突检测报告" if not pillar else f"规则冲突检测 — {pillar}"
        result_lines.append(f"⚠️ {title}")
        
        if not conflicts:
            result_lines.append(f"✅ 未发现冲突")
            return AnalysisResponse(result="\n".join(result_lines), data={"conflicts": [], "total": 0})
        
        by_severity = {"high": [], "medium": [], "low": []}
        for c in conflicts:
            by_severity.setdefault(c["severity"], []).append(c)
        
        for sev, label in [("high", "🔴 高风险"), ("medium", "🟡 中风险"), ("low", "🟢 低风险")]:
            items = by_severity.get(sev, [])
            if items:
                result_lines.append(f"\n{label} ({len(items)} 个):")
                for c in items[:10]:
                    result_lines.append(f"  • {c['description']}")
        
        result_lines.append(f"\n📊 总计: {len(conflicts)} 个冲突")
        result_lines.append(f"  🔴 高风险: {len(by_severity.get('high', []))}")
        result_lines.append(f"  🟡 中风险: {len(by_severity.get('medium', []))}")
        result_lines.append(f"  🟢 低风险: {len(by_severity.get('low', []))}")
        
        return AnalysisResponse(
            result="\n".join(result_lines),
            data={"conflicts": conflicts, "total": len(conflicts), "by_severity": by_severity}
        )
    
    except Exception as e:
        raise HTTPException(500, f"检测失败: {str(e)}")
    finally:
        if analysis_dir in sys.path:
            sys.path.remove(analysis_dir)


@router.get("/api/v1/agent/coverage", summary="规则覆盖率分析")
def coverage_analysis(pillar: str = None):
    """分析规则测试覆盖率"""
    analysis_dir = os.path.join(os.path.dirname(__file__), "../../tools/audit-assistant/analysis")
    sys.path.insert(0, analysis_dir)
    
    try:
        import coverage_analysis as ca
        
        conn = ca.get_conn()
        conn.row_factory = __import__('sqlite3').Row
        stats = ca.analyze_coverage(conn, pillar)
        conn.close()
        
        result_lines = []
        result_lines.append(f"📈 规则覆盖率分析报告")
        result_lines.append(f"总规则数: {stats['total_rules']}")
        result_lines.append(f"DRG 规则数: {stats['drg_total']}")
        result_lines.append(f"✅ 已覆盖: {stats['covered']}")
        result_lines.append(f"❌ 未覆盖: {stats['uncovered']}")
        result_lines.append(f"📊 覆盖率: {stats['coverage_pct']}%")
        
        result_lines.append(f"\n按支柱分布:")
        for p, c in sorted(stats["by_pillar"].items()):
            result_lines.append(f"  {p}: {c} 条")
        
        result_lines.append(f"\n按规则类别覆盖率:")
        for cat in stats["by_category"][:10]:
            bar = "█" * int(cat["coverage_pct"] / 10) + "░" * (10 - int(cat["coverage_pct"] / 10))
            result_lines.append(f"  {bar} {cat['category']} {cat['covered']}/{cat['total']} ({cat['coverage_pct']}%)")
        
        if len(stats["by_category"]) > 10:
            result_lines.append(f"  ... 还有 {len(stats['by_category']) - 10} 个类别")
        
        if stats["uncovered_rules"]:
            result_lines.append(f"\n未覆盖规则示例:")
            for r in stats["uncovered_rules"][:10]:
                result_lines.append(f"  • {r['code']} ({r['category']}) [{r['pillar']}/{r['stage']}]")
        
        result_lines.append(f"\n💡 建议: 运行 /gen-tests 从 RULE_BOOK.md 补全测试")
        
        return AnalysisResponse(
            result="\n".join(result_lines),
            data=stats
        )
    
    except Exception as e:
        raise HTTPException(500, f"分析失败: {str(e)}")
    finally:
        if analysis_dir in sys.path:
            sys.path.remove(analysis_dir)