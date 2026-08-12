# -*- coding: utf-8 -*-
"""同步值班监控数据/报告到 GitHub 仓库（GitHub Pages 查询）

功能：
1. 汇总各供电所查岗统计，生成 summary.json
2. 复制最新值班报告到仓库 reports 目录
3. 提交并推送到 GitHub 仓库

用法: python sync_to_github.py [日期YYYY-MM-DD]   (默认最新有数据日期)
"""
import os
import sys
import json
import shutil
import datetime
import subprocess

DUTY = r"C:\Users\Administrator\Documents\lingxi-claw\20260810-14-51-58-946\output\duty_monitor"
DEPLOY = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(DUTY, "data")
REPORTS = os.path.join(DUTY, "reports")
REMOTE = "https://github.com/wsmcmtlg/duty_monitor.git"


def find_latest_date():
    files = [f[:-5] for f in os.listdir(DATA) if f.endswith(".json")] if os.path.isdir(DATA) else []
    files.sort(reverse=True)
    return files[0] if files else None


def build_summary(records):
    agg = {}
    for rec in records:
        name = rec["name"]
        a = agg.setdefault(name, {"name": name, "checks": 0, "person_checks": 0,
                                  "empty_checks": 0, "offline": 0})
        a["checks"] += 1
        if rec.get("online", True):
            if rec.get("has_person"):
                a["person_checks"] += 1
            else:
                a["empty_checks"] += 1
        else:
            a["offline"] += 1
    for a in agg.values():
        base = a["checks"] - a["offline"]
        a["duty_rate"] = (a["person_checks"] / base) if base else 0.0
    return list(agg.values())


def collect_reports():
    out_dir = os.path.join(DEPLOY, "reports")
    os.makedirs(out_dir, exist_ok=True)
    files = []
    if os.path.isdir(REPORTS):
        for f in sorted(os.listdir(REPORTS), reverse=True):
            if f.endswith((".docx", ".xlsx")):
                src = os.path.join(REPORTS, f)
                dst = os.path.join(out_dir, f)
                shutil.copy(src, dst)
                files.append({"name": f, "size": round(os.path.getsize(dst) / 1024, 1),
                              "mtime": datetime.datetime.fromtimestamp(os.path.getmtime(src)).strftime("%Y-%m-%d %H:%M"),
                              "file": "reports/" + f})
    return files[:30]  # 最多保留30份


def sync(date_str=None):
    if date_str is None:
        date_str = find_latest_date()
    if not date_str:
        print("无查岗数据，无法同步")
        return
    dfile = os.path.join(DATA, date_str + ".json")
    if not os.path.exists(dfile):
        print(f"{date_str} 无数据文件")
        return
    with open(dfile, encoding="utf-8") as f:
        rounds = json.load(f)
    records = [rec for rd in rounds for rec in rd["records"]]
    summary = build_summary(records)

    total_checks = sum(a["checks"] for a in summary)
    total_empty = sum(a["empty_checks"] for a in summary)
    total_person = sum(a["person_checks"] for a in summary)
    base = sum(a["checks"] - a["offline"] for a in summary)
    rate = (total_person / base) if base else 0.0

    reports = collect_reports()
    data = {
        "date": date_str,
        "total_su": len(summary),
        "total_checks": total_checks,
        "total_empty": total_empty,
        "rate": round(rate, 4),
        "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": summary,
        "reports": reports,
    }
    with open(os.path.join(DEPLOY, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已生成 summary.json（{date_str}）供电所{len(summary)} 查岗{total_checks} 无人{total_empty}")

    # git 提交推送
    os.chdir(DEPLOY)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", f"同步值班数据 {date_str}"], check=False)
    r = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
    print("推送:", "成功" if r.returncode == 0 else r.stderr[:300])
    return r.returncode


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    sync(date)
