import os


class Config:
    BASEDIR = os.path.abspath(os.path.dirname(__file__))

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-change-me'

    # Always use an absolute path to avoid sqlite "unable to open database file" on Windows.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or (
        'sqlite:///' + os.path.join(BASEDIR, 'data', 'habits.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Simple app defaults
    DEFAULT_HEATMAP_DAYS = 140
    SUCCESS_RATE_DAYS = 30
