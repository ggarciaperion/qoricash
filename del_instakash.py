from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    for slug in ('instakash', 'metafxperu'):
        db.session.execute(db.text(f"DELETE FROM fx_change_events WHERE competitor_id=(SELECT id FROM fx_competitors WHERE slug='{slug}')"))
        db.session.execute(db.text(f"DELETE FROM fx_rate_history WHERE competitor_id=(SELECT id FROM fx_competitors WHERE slug='{slug}')"))
        db.session.execute(db.text(f"DELETE FROM fx_rate_current WHERE competitor_id=(SELECT id FROM fx_competitors WHERE slug='{slug}')"))
        db.session.execute(db.text(f"DELETE FROM fx_competitors WHERE slug='{slug}'"))
        print(f'{slug} eliminado')
    db.session.commit()
    print('Listo.')
