def normalize_log(entry):
    labels = entry["labels"]
    return {
        "time": entry["timestamp"],
        "source": f"{labels.get('namespace')}/{labels.get('container')}",
        "pod": labels.get("pod"),
        "node": labels.get("node"),
        "message": entry["message"],
    }


def build_llm_prompt(normalized_logs, time_range):
    header = (
        f"Cluster: homelab\n"
        f"Time window: {time_range.start.isoformat()} → {time_range.end.isoformat()}\n\n"
        "Logs:\n"
    )

    lines = []
    for log in normalized_logs:
        lines.append(
            f"[{log['time']}] {log['source']} "
            f"(pod={log.get('pod')}, node={log.get('node')})\n"
            f"{log['message']}"
        )

    return header + "\n\n".join(lines)


def build_text_header(normalized_logs, time_range):
    lines = [
        "=== Log Analyzer ===",
        "Cluster: homelab",
        f"Time Window: {time_range.start.date()} → {time_range.end.date()}",
        f"Log Count: {len(normalized_logs)}",
        "",
        "--- Logs ---",
    ]

    for log in normalized_logs:
        lines.append(
            f"[{log['time']}] {log['source']} "
            f"(pod={log.get('pod')}, node={log.get('node')})"
        )
        lines.append(log["message"])
        lines.append("")

    lines.append("--- Analysis ---")
    lines.append("")  # blank line before streaming starts
    return "\n".join(lines)
