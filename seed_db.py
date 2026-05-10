from app import app, db
from models import Category

default_categories = [
    "Appliance",
    "Audio",
    "Gaming",
    "Laptops",
    "Phones",
    "TVs",
    "Fridge"
]

with app.app_context():
    # Drop all tables and recreate them
    db.drop_all()
    db.create_all()
    
    # Seed default categories
    for cat_name in default_categories:
        new_category = Category(name=cat_name)
        db.session.add(new_category)
        
    db.session.commit()
    print("Database recreated and default categories seeded successfully!")
