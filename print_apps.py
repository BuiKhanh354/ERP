from ERP.settings import INSTALLED_APPS
for i, app in enumerate(INSTALLED_APPS):
    print(f"[{i}] {repr(app)}")
