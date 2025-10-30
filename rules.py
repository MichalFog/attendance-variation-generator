from datetime import datetime, timedelta
import hashlib
import pandas as pd

class AttendanceVariationRules:
    def apply(self, df, report_type):
        if df.empty:
            return pd.DataFrame(), []

        def parse_time(value: str):
            try:
                return datetime.strptime(value, "%H:%M")
            except Exception:
                return None

        def compute_hours(t0: datetime, t1: datetime) -> float:
            delta = (t1 - t0).total_seconds() / 3600
            if delta < 0:
                delta += 24  # overnight
            return round(delta, 2)

        new_rows, log = [], []
        for i, row in df.iterrows():
            date = row.get("date", "")
            start = str(row.get("start", "") or "")
            end = str(row.get("end", "") or "")
            hours_val = row.get("hours", 0) or 0.0

            t0 = parse_time(start)
            t1 = parse_time(end)

            # Case 1: both times present and sensible → keep as-is
            if t0 and t1:
                hours_computed = compute_hours(t0, t1)
                if 0.25 <= hours_computed <= 16:
                    new_rows.append({
                        "date": date,
                        "start": start,
                        "end": end,
                        "hours": round(hours_computed, 2),
                        "break": row.get("break", ""),
                        "raw_line": row.get("raw_line", ""),
                    })
                    log.append(f"Row {i}: kept {start}-{end} ({hours_computed:.2f}h)")
                    continue
                # If out of range, minimally fix: ensure end after start by 30m
                t1_fixed = t0 + timedelta(minutes=30)
                hours_fixed = compute_hours(t0, t1_fixed)
                new_rows.append({
                    "date": date,
                    "start": start,
                    "end": t1_fixed.strftime("%H:%M"),
                    "hours": hours_fixed,
                    "break": row.get("break", ""),
                    "raw_line": row.get("raw_line", ""),
                })
                log.append(f"Row {i}: fixed end to {t1_fixed.strftime('%H:%M')} (was {end})")
                continue

            # Case 2: only one time present → keep time, hours 0.0
            if t0 and not t1:
                new_rows.append({
                    "date": date,
                    "start": start,
                    "end": end,
                    "hours": 0.0,
                    "break": row.get("break", ""),
                    "raw_line": row.get("raw_line", ""),
                })
                log.append(f"Row {i}: missing end; hours set to 0.00")
                continue
            if t1 and not t0:
                new_rows.append({
                    "date": date,
                    "start": start,
                    "end": end,
                    "hours": 0.0,
                    "break": row.get("break", ""),
                    "raw_line": row.get("raw_line", ""),
                })
                log.append(f"Row {i}: missing start; hours set to 0.00")
                continue

            # Case 3: no valid times; keep hours if positive else 0.0
            hours_clean = float(hours_val) if hours_val and hours_val > 0 else 0.0
            new_rows.append({
                "date": date,
                "start": start,
                "end": end,
                "hours": round(hours_clean, 2),
                "break": row.get("break", ""),
                "raw_line": row.get("raw_line", ""),
            })
            log.append(f"Row {i}: no times; hours kept {hours_clean:.2f}")

        final_df = pd.DataFrame(new_rows)
        final_df['weekday'] = final_df['date'].apply(self._hebrew_weekday)
        if report_type == 'A':
            final_df['is_sat'] = final_df.apply(
                lambda r: 'כן' if r['weekday'] == 'שבת' else '',
                axis=1
            )

        return final_df, log

    @staticmethod
    def _hebrew_weekday(date_text: str) -> str:
        if not isinstance(date_text, str) or not date_text:
            return ""
        try:
            names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
            return names[datetime.strptime(date_text, '%Y-%m-%d').weekday()]
        except (ValueError, IndexError):
            return ""