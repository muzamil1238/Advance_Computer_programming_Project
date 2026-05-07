from __future__ import annotations

from datetime import datetime

from extensions import db


class Habit(db.Model):
    __tablename__ = "habits"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), nullable=False, default="Other")
    target_per_week = db.Column(db.Integer, nullable=False, default=7)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    entries = db.relationship(
        "HabitEntry",
        back_populates="habit",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Habit id={self.id} name={self.name!r}>"