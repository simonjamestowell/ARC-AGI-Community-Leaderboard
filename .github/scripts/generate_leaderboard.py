#!/usr/bin/env python3
"""
Generate the leaderboard table in README.md and a leaderboard.json file
from all submission YAML files.

README table  — for browsing on GitHub (one section per ARC version)
leaderboard.json — for the website to consume

Run automatically via GitHub Actions on merge to main, or manually:
    python generate_leaderboard.py
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone

import yaml

SUBMISSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "submissions")
README_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "README.md")
JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "leaderboard.json")

START_MARKER = "<!-- LEADERBOARD:START - Do not remove or modify this section -->"
END_MARKER = "<!-- LEADERBOARD:END -->"

# Display order for benchmark versions
ARC_VERSION_ORDER = ["arc-agi-3", "arc-agi-2", "arc-agi-1"]
ARC_VERSION_LABELS = {
    "arc-agi-1": "ARC-AGI-1",
    "arc-agi-2": "ARC-AGI-2",
    "arc-agi-3": "ARC-AGI-3",
}


def load_submissions():
    """Load all submission YAML files and return a list of parsed entries."""
    entries = []

    for dirname in os.listdir(SUBMISSIONS_DIR):
        if dirname.startswith("."):
            continue
        yaml_path = os.path.join(SUBMISSIONS_DIR, dirname, "submission.yaml")
        if not os.path.isfile(yaml_path):
            continue

        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"  ⚠ Skipping {dirname}: {e}")
            continue

        if not isinstance(data, dict):
            continue

        versions = data.get("versions", [])
        if not versions:
            continue

        latest = versions[-1]

        # Collect best score per benchmark across all versions
        best_scores = {}
        all_benchmarks = set()
        for v in versions:
            scores = v.get("scores", {})
            if isinstance(scores, dict):
                for benchmark, score in scores.items():
                    all_benchmarks.add(benchmark)
                    if benchmark not in best_scores or score > best_scores[benchmark]:
                        best_scores[benchmark] = score

        # Format authors
        authors = data.get("authors", [])
        author_str = ", ".join(a.get("name", "Unknown") for a in authors if isinstance(a, dict))

        # Format models from latest version
        models = latest.get("models", [])
        model_str = ", ".join(
            m.get('name', '?')
            for m in models if isinstance(m, dict)
        )

        # Structured author list for JSON
        authors_structured = [
            {
                "name": a.get("name", "Unknown"),
                "affiliation": a.get("affiliation", ""),
                "url": a.get("url", ""),
                "twitter": a.get("twitter", ""),
            }
            for a in authors if isinstance(a, dict)
        ]

        # Structured version list for JSON (convert dates to strings)
        versions_structured = []
        for v in versions:
            vs = dict(v)
            if "date" in vs and not isinstance(vs["date"], str):
                vs["date"] = str(vs["date"])
            versions_structured.append(vs)

        entries.append({
            "id": dirname,
            "name": data.get("name", dirname),
            "authors": author_str,
            "authors_detail": authors_structured,
            "description": data.get("description", ""),
            "best_scores": best_scores,
            "benchmarks": sorted(all_benchmarks),
            "latest_version": latest.get("version", "?"),
            "models": model_str,
            "code_url": data.get("code_url", ""),
            "paper_url": data.get("paper_url", ""),
            "twitter_url": data.get("twitter_url", ""),
            "versions": versions_structured,
        })

    return entries


def generate_table(entries):
    """Generate markdown tables grouped by ARC version."""
    if not entries:
        return "*No submissions yet.*"

    # Group entries by which benchmarks they have scores for
    by_benchmark = defaultdict(list)
    for entry in entries:
        for benchmark in entry["best_scores"]:
            by_benchmark[benchmark].append(entry)

    sections = []
    for arc_ver in ARC_VERSION_ORDER:
        if arc_ver not in by_benchmark:
            continue

        label = ARC_VERSION_LABELS.get(arc_ver, arc_ver)
        benchmark_entries = sorted(
            by_benchmark[arc_ver],
            key=lambda e: e["best_scores"].get(arc_ver, 0),
            reverse=True,
        )

        header = f"### {label}\n"
        table_header = "| Rank | Name | Authors | Score | Models | Code |"
        separator = "|------|------|---------|-------|--------|------|"

        rows = [header, table_header, separator]
        for i, entry in enumerate(benchmark_entries, 1):
            score = entry["best_scores"].get(arc_ver, 0)
            code_link = f"[Repo]({entry['code_url']})" if entry["code_url"] else ""
            row = f"| {i} | {entry['name']} | {entry['authors']} | {score}% | {entry['models']} | {code_link} |"
            rows.append(row)

        sections.append("\n".join(rows))

    return "\n\n".join(sections)


def generate_json(entries):
    """Write a JSON file for the website to consume."""
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "submissions": [],
    }

    for entry in entries:
        output["submissions"].append({
            "id": entry["id"],
            "name": entry["name"],
            "authors": entry["authors_detail"],
            "description": entry["description"],
            "best_scores": entry["best_scores"],
            "benchmarks": entry["benchmarks"],
            "latest_version": entry["latest_version"],
            "code_url": entry["code_url"],
            "paper_url": entry["paper_url"],
            "twitter_url": entry["twitter_url"],
            "versions": entry["versions"],
        })

    with open(JSON_PATH, "w") as f:
        json.dump(output, f, indent=2)


def update_readme(table):
    """Replace the leaderboard section in README.md."""
    with open(README_PATH, "r") as f:
        content = f.read()

    start_idx = content.index(START_MARKER) + len(START_MARKER)
    end_idx = content.index(END_MARKER)

    new_content = content[:start_idx] + "\n" + table + "\n" + content[end_idx:]

    with open(README_PATH, "w") as f:
        f.write(new_content)


def main():
    print("Generating leaderboard...")
    entries = load_submissions()
    print(f"  Found {len(entries)} submission(s)")

    table = generate_table(entries)
    update_readme(table)
    print("  README.md updated ✓")

    generate_json(entries)
    print("  leaderboard.json updated ✓")


if __name__ == "__main__":
    main()
