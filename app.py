from __future__ import annotations

import csv
import io
import os
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for

from config import Config
from extensions import db
from models.habit import Habit
from models.habit_entry import HabitEntry


def _today_str() -> str:
    return date.today().isoformat()


def _clamp_int(value: str | None, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except Exception:
        return default
    return max(min_value, min(max_value, parsed))


def _ensure_dirs(app: Flask) -> None:
    os.makedirs(os.path.join(app.root_path, "data"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "logs"), exist_ok=True)


def _seed_defaults() -> None:
    if Habit.query.count() > 0:
        return
    defaults = [
        Habit(name="Morning Exercise", category="Fitness", target_per_week=4),
        Habit(name="Drink Water", category="Health", target_per_week=7),
        Habit(name="Read 20 Pages", category="Learning", target_per_week=5),
        Habit(name="Meditate", category="Mindfulness", target_per_week=6),
    ]
    db.session.add_all(defaults)
    db.session.commit()


def _entries_for_day(day_str: str) -> dict[int, HabitEntry]:
    return {e.habit_id: e for e in HabitEntry.query.filter_by(date=day_str).all()}


def _is_perfect_day(habits: list[Habit], entries_by_habit_id: dict[int, HabitEntry]) -> bool:
    if not habits:
        return False
    for h in habits:
        e = entries_by_habit_id.get(h.id)
        if not e or not e.completed:
            return False
    return True


def _overall_streak(habits: list[Habit]) -> int:
    if not habits:
        return 0
    streak = 0
    cursor = date.today()
    for _ in range(3650):
        ds = cursor.isoformat()
        if _is_perfect_day(habits, _entries_for_day(ds)):
            streak += 1
            cursor -= timedelta(days=1)
        else:
            break
    return streak


def _success_rate_last_days(habits: list[Habit], days: int) -> float:
    if not habits:
        return 0.0
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    completed = HabitEntry.query.filter(HabitEntry.date >= start, HabitEntry.completed.is_(True)).count()
    denom = len(habits) * days
    return (completed / denom) if denom else 0.0


def _heatmap_series(habits: list[Habit], days: int) -> list[dict]:
    if not habits:
        return []
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = HabitEntry.query.filter(HabitEntry.date >= start, HabitEntry.completed.is_(True)).all()
    completed_by_day: dict[str, int] = defaultdict(int)
    for r in rows:
        completed_by_day[r.date] += 1

    out: list[dict] = []
    total = len(habits)
    for i in range(days):
        d = (date.today() - timedelta(days=(days - 1 - i))).isoformat()
        c = completed_by_day.get(d, 0)
        out.append({"date": d, "completed": c, "total": total, "ratio": (c / total) if total else 0})
    return out


def _insights(habits: list[Habit]) -> list[dict]:
    if not habits:
        return [{"title": "Create your first habit", "message": "Add a habit and start your first streak today.", "level": "info"}]

    tips: list[dict] = []
    start7 = (date.today() - timedelta(days=6)).isoformat()
    for h in habits:
        done = HabitEntry.query.filter(
            HabitEntry.habit_id == h.id,
            HabitEntry.date >= start7,
            HabitEntry.completed.is_(True),
        ).count()
        target = max(1, h.target_per_week)
        if (done / target) < 0.5:
            tips.append({
                "title": f"{h.name} is slipping",
                "message": f"You’re at {done}/{target} this week. Try scheduling it after an existing routine (e.g., after breakfast).",
                "level": "warning",
            })

    if not tips:
        tips.append({
            "title": "You’re consistent",
            "message": "Great momentum this week. Consider raising one target slightly or adding a new habit.",
            "level": "success",
        })
    return tips[:6]


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        _ensure_dirs(app)
        db.create_all()
        _seed_defaults()

    # ---------------- Pages ----------------
    @app.get("/")
    def index():
        habits = Habit.query.order_by(Habit.created_at.desc()).all()
        today = _today_str()
        today_entries = _entries_for_day(today)
        for h in habits:
            e = today_entries.get(h.id)
            h.today_completed = bool(e and e.completed)  # type: ignore[attr-defined]
            h.today_notes = (e.notes or "") if e else ""  # type: ignore[attr-defined]

        streak = _overall_streak(habits)
        success_rate = _success_rate_last_days(habits, app.config.get("SUCCESS_RATE_DAYS", 30))
        heatmap = _heatmap_series(habits, app.config.get("DEFAULT_HEATMAP_DAYS", 140))
        return render_template(
            "index.html",
            habits=habits,
            today=today,
            streak=streak,
            success_rate=round(success_rate * 100, 1),
            heatmap=heatmap,
        )

    @app.get("/history")
    def history():
        entries = HabitEntry.query.join(Habit).order_by(HabitEntry.date.desc(), Habit.name.asc()).all()
        return render_template("history.html", entries=entries)

    @app.get("/analytics")
    def analytics():
        return render_template("analytics.html")

    @app.get("/insights")
    def insights():
        habits = Habit.query.order_by(Habit.created_at.desc()).all()
        return render_template("insights.html", tips=_insights(habits))

    # ---------------- Habits CRUD ----------------
    @app.post("/habits")
    def create_habit():
        name = (request.form.get("name") or "").strip()
        category = (request.form.get("category") or "Other").strip() or "Other"
        target = _clamp_int(request.form.get("target_per_week"), default=7, min_value=1, max_value=14)
        if not name:
            flash("Habit name is required.", "error")
            return redirect(url_for("index"))
        db.session.add(Habit(name=name, category=category, target_per_week=target))
        db.session.commit()
        flash("Habit added.", "success")
        return redirect(url_for("index"))

    @app.post("/habits/<int:habit_id>")
    def update_habit(habit_id: int):
        habit = Habit.query.get_or_404(habit_id)
        name = (request.form.get("name") or "").strip()
        category = (request.form.get("category") or "Other").strip() or "Other"
        target = _clamp_int(request.form.get("target_per_week"), default=habit.target_per_week, min_value=1, max_value=14)
        if not name:
            flash("Habit name is required.", "error")
            return redirect(url_for("index"))
        habit.name = name
        habit.category = category
        habit.target_per_week = target
        db.session.commit()
        flash("Habit updated.", "success")
        return redirect(url_for("index"))

    @app.post("/habits/<int:habit_id>/delete")
    def delete_habit(habit_id: int):
        habit = Habit.query.get_or_404(habit_id)
        db.session.delete(habit)
        db.session.commit()
        flash("Habit deleted.", "success")
        return redirect(url_for("index"))

    # --------------- Check-in API ---------------
    @app.post("/api/checkin")
    def api_checkin():
        payload = request.get_json(silent=True) or {}
        habit_id = int(payload.get("habit_id") or 0)
        completed = bool(payload.get("completed"))
        notes = (payload.get("notes") or "").strip()
        ds = (payload.get("date") or _today_str()).strip()

        habit = Habit.query.get_or_404(habit_id)
        entry = HabitEntry.query.filter_by(habit_id=habit.id, date=ds).first()
        if entry is None:
            entry = HabitEntry(habit_id=habit.id, date=ds)
            db.session.add(entry)
        entry.completed = completed
        entry.notes = notes
        db.session.commit()

        habits = Habit.query.all()
        return jsonify({
            "ok": True,
            "habit_id": habit.id,
            "date": ds,
            "completed": entry.completed,
            "streak": _overall_streak(habits),
            "success_rate": round(_success_rate_last_days(habits, app.config.get("SUCCESS_RATE_DAYS", 30)) * 100, 1),
        })

    # --------------- Analytics API ---------------
    @app.get("/api/analytics/summary")
    def api_analytics_summary():
        habits = Habit.query.all()
        days = int(app.config.get("SUCCESS_RATE_DAYS", 30))
        start = (date.today() - timedelta(days=days - 1)).isoformat()
        rows = HabitEntry.query.filter(HabitEntry.date >= start).all()

        total = len(habits)
        completed_by_day: dict[str, int] = defaultdict(int)
        for r in rows:
            if r.completed:
                completed_by_day[r.date] += 1

        labels: list[str] = []
        daily_rates: list[float] = []
        streak_series: list[int] = []
        running = 0
        for i in range(days):
            d = (date.today() - timedelta(days=(days - 1 - i))).isoformat()
            c = completed_by_day.get(d, 0)
            labels.append(d)
            daily_rates.append(round(((c / total) * 100) if total else 0, 2))
            is_perfect = bool(total and c == total)
            running = (running + 1) if is_perfect else 0
            streak_series.append(running)

        # Monthly (last 12 months)
        month_labels: list[str] = []
        month_rates: list[float] = []
        first_this_month = date.today().replace(day=1)
        for m in range(11, -1, -1):
            first = (first_this_month - timedelta(days=30 * m)).replace(day=1)
            if first.month == 12:
                next_month = first.replace(year=first.year + 1, month=1)
            else:
                next_month = first.replace(month=first.month + 1)
            start_s = first.isoformat()
            end_s = next_month.isoformat()
            completed = HabitEntry.query.filter(
                HabitEntry.date >= start_s,
                HabitEntry.date < end_s,
                HabitEntry.completed.is_(True),
            ).count()
            days_in_month = (next_month - first).days
            denom = (len(habits) * days_in_month) if habits else 0
            month_labels.append(first.strftime("%b %Y"))
            month_rates.append(round(((completed / denom) * 100) if denom else 0, 2))

        return jsonify({
            "ok": True,
            "kpis": {
                "habits": len(habits),
                "streak": _overall_streak(habits),
                "success_rate": round(_success_rate_last_days(habits, days) * 100, 1),
            },
            "daily": {"labels": labels, "success_rate": daily_rates, "streak": streak_series},
            "monthly": {"labels": month_labels, "success_rate": month_rates},
        })

    # --------------- Exports ---------------
    @app.get("/export/csv")
    def export_csv():
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["type", "id", "habit_id", "habit_name", "category", "target_per_week", "date", "completed", "notes"])

        habits = Habit.query.order_by(Habit.id.asc()).all()
        for h in habits:
            writer.writerow(["habit", h.id, "", h.name, h.category, h.target_per_week, "", "", ""])

        entries = HabitEntry.query.join(Habit).order_by(HabitEntry.date.asc(), Habit.name.asc()).all()
        for e in entries:
            writer.writerow([
                "entry",
                e.id,
                e.habit_id,
                e.habit.name if e.habit else "",
                e.habit.category if e.habit else "",
                e.habit.target_per_week if e.habit else "",
                e.date,
                int(bool(e.completed)),
                (e.notes or ""),
            ])

        data = out.getvalue().encode("utf-8")
        return Response(data, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=habit_tracker_export.csv"})

    @app.get("/export/pdf")
    def export_pdf():
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except Exception:
            return ("PDF export requires 'reportlab'. Install it with: pip install reportlab", 501)

        habits = Habit.query.order_by(Habit.created_at.desc()).all()
        streak = _overall_streak(habits)
        success = round(_success_rate_last_days(habits, 30) * 100, 1)

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - 54
        c.setFont("Helvetica-Bold", 16)
        c.drawString(54, y, "Personal Habit Tracker — Report")
        y -= 22
        c.setFont("Helvetica", 11)
        c.drawString(54, y, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        y -= 18
        c.drawString(54, y, f"Current streak: {streak} days")
        y -= 16
        c.drawString(54, y, f"Success rate (last 30 days): {success}%")
        y -= 26
        c.setFont("Helvetica-Bold", 12)
        c.drawString(54, y, "Habits")
        y -= 18
        c.setFont("Helvetica", 10)
        for h in habits[:30]:
            c.drawString(54, y, f"• {h.name} ({h.category}) — target/week: {h.target_per_week}")
            y -= 14
            if y < 72:
                c.showPage()
                y = height - 54
                c.setFont("Helvetica", 10)
        c.save()
        buffer.seek(0)

        return Response(buffer.getvalue(), mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=habit_tracker_report.pdf"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)