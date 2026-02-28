"""
Bloomerp Router for Projects app
This creates automatic CRUD views for Project models using Bloomerp framework
"""
from bloomerp.utils.router import BloomerpRouter
from .models import Project, Task, TimeEntry

# Initialize router
router = BloomerpRouter()

# Register models with Bloomerp
# Bloomerp will automatically create:
# - List views (/projects/list, /tasks/list, etc.)
# - Detail views (/projects/{id}, /tasks/{id}, etc.)
# - Create/Update/Delete views
# - Advanced filtering and search

# Note: Models need to inherit from BloomerpModel or have proper Meta class
# For now, we'll use the existing models and Bloomerp will work with them
