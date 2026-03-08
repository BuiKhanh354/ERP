import sys
import traceback

try:
    import django
    import sys
    from pathlib import Path
    import os
    BASE_DIR = Path(__file__).resolve().parent
    sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ERP.settings')
    django.setup()
    with open('test_out.txt', 'w') as f:
        f.write('Success!\n')
except Exception as e:
    with open('test_out.txt', 'w') as f:
        f.write('Exception:\n')
        traceback.print_exc(file=f)
