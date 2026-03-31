"""
Secuencia de numeración para asientos contables.
Garantiza unicidad y secuencialidad por año mediante SELECT FOR UPDATE.
"""
from app.extensions import db


class JournalSequence(db.Model):
    __tablename__ = 'journal_sequences'

    year        = db.Column(db.Integer, primary_key=True)
    last_number = db.Column(db.Integer, default=0, nullable=False)

    def __repr__(self):
        return f'<JournalSequence {self.year}: {self.last_number}>'
