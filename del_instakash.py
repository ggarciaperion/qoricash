from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    db.session.execute(db.text("DELETE FROM fx_change_events WHERE competitor_id=(SELECT id FROM fx_competitors WHERE slug='instakash')"))
    db.session.execute(db.text("DELETE FROM fx_rate_history WHERE competitor_id=(SELECT id FROM fx_competitors WHERE slug='instakash')"))
    db.session.execute(db.text("DELETE FROM fx_rate_current WHERE competitor_id=(SELECT id FROM fx_competitors WHERE slug='instakash')"))
    db.session.execute(db.text("DELETE FROM fx_competitors WHERE slug='instakash'"))
    db.session.commit()
    print('Instakash eliminado correctamente')
