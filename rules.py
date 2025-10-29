def apply_rules(df, report_type):
    """
    Apply deterministic, reasonable, per-type modifications to the attendance data.
    Goals:
    - Keep structure: date, start, end, hours
    - Ensure end > start (allowing overnight by +24h)
    - Deterministically perturb times based on date and type (no randomness)
    - Clamp daily hours to a realistic range [4.0, 12.0]
    - Preserve missing/invalid rows gracefully

    Returns: (new_df, log)
    """
    from datetime import datetime, timedelta
    import hashlib

    def parse_time_safe(value: str):
        try:
            return datetime.strptime(value, "%H:%M")
        except Exception:
            return None

    def deterministic_minutes(date_text: str, base: int) -> int:
        """Map date string to a small minute delta deterministically."""
        key = f"{report_type}|{date_text}|{base}".encode("utf-8")
        h = hashlib.sha256(key).hexdigest()
        # Map to {-10, -5, 0, +5, +10} minutes
        bucket = int(h[:2], 16) % 5
        return [-10, -5, 0, 5, 10][bucket]

    new_rows = []
    log = []

    for i, row in df.iterrows():
        date_text = str(row.get("date", "")).strip()
        start_text = str(row.get("start", "")).strip()
        end_text = str(row.get("end", "")).strip()

        t_start = parse_time_safe(start_text)
        t_end = parse_time_safe(end_text)

        # If both times exist, apply per-type perturbations
        if t_start and t_end:
            # Base deterministic deltas
            start_delta = deterministic_minutes(date_text, 1)
            end_delta = deterministic_minutes(date_text, 2)

            if report_type == "A":
                # Type A: generally shift start slightly later, end slightly later
                start_delta = max(0, start_delta)  # 0, +5, +10
                end_delta = max(0, end_delta)      # 0, +5, +10
            elif report_type == "B":
                # Type B: shift start earlier, end earlier
                start_delta = min(0, start_delta)  # -10, -5, 0
                end_delta = min(0, end_delta)      # -10, -5, 0

            t_start_new = t_start + timedelta(minutes=start_delta)
            t_end_new = t_end + timedelta(minutes=end_delta)

            # Ensure logical ordering: if end <= start, push end forward by 30-120 min deterministically
            if t_end_new <= t_start_new:
                fix_delta = 30 + (abs(deterministic_minutes(date_text, 3)) * 9)  # 30..120
                t_end_new = t_start_new + timedelta(minutes=fix_delta)

            # Compute hours with overnight handling
            duration_hours = (t_end_new - t_start_new).total_seconds() / 3600.0
            if duration_hours <= 0:
                duration_hours += 24.0

            # Clamp to realistic bounds
            if duration_hours < 4.0:
                bump = 4.0 - duration_hours
                t_end_new += timedelta(hours=bump)
                duration_hours = 4.0
            elif duration_hours > 12.0:
                reduce = duration_hours - 12.0
                t_end_new -= timedelta(hours=reduce)
                duration_hours = 12.0

            new_start = t_start_new.strftime("%H:%M")
            new_end = t_end_new.strftime("%H:%M")
            new_hours = round(duration_hours, 2)

            log.append(
                f"Row {i} ({date_text}): {start_text}-{end_text} -> {new_start}-{new_end} ({new_hours}h)"
            )
        else:
            # If missing times, keep as-is but ensure hours is 0.0-8.0 deterministic
            base_hours = row.get("hours", 0) or 0.0
            if not isinstance(base_hours, (int, float)):
                base_hours = 0.0
            # Snap to deterministic bucket
            bucket = (abs(deterministic_minutes(date_text, 4)) // 5)  # 0..2
            fallback_hours = [6.0, 7.5, 8.0][bucket]
            new_hours = round(base_hours if base_hours > 0 else fallback_hours, 2)
            new_start = start_text
            new_end = end_text
            log.append(f"Row {i} ({date_text}): kept times, hours={new_hours}")

        new_rows.append({
            "date": date_text,
            "start": new_start,
            "end": new_end,
            "hours": new_hours,
        })

    return (df.__class__(new_rows), log)