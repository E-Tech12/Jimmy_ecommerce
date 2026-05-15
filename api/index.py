import os
import sys

# Add the parent directory to sys.path so we can import app.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel needs the app variable to be available
# We can also rename it to 'handler' if needed, but 'app' usually works
