"""Format only persisted decision trace facts."""
def explain(trace_rows):
    if not trace_rows:
        return "No recorded decision."
    row = trace_rows[0]
    lines = [row["summary"], f"Decision recorded at graph revision {row['revision']}."]
    for plan in row["plans"]:
        if plan["selected"]:
            lines.append("Selected: " + " → ".join(plan["actions"]) + ".")
        elif plan["rejected_reason"]:
            lines.append(f"Rejected {plan['plan']}: {plan['rejected_reason']}")
    return "\n".join(lines)
