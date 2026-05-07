from __future__ import annotations

from extensions import db


class HabitEntry(db.Model):
    __tablename__ = "habit_entries"

    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey("habits.id"), nullable=False, index=True)

    # Store as YYYY-MM-DD string for simple sorting/ranging without migrations.
    date = db.Column(db.String(10), nullable=False, index=True)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=True)

    habit = db.relationship("Habit", back_populates="entries")

    __table_args__ = (
        db.UniqueConstraint("habit_id", "date", name="uq_habit_entries_habit_date"),
    )

    def __repr__(self) -> str:
        return f"<HabitEntry habit_id={self.habit_id} date={self.date} completed={self.completed}>"