"""
Script to extract inline CSS and JS from HTML templates into separate files.

Strategy:
1. CSS: Always extract to external files
2. JS: If it contains Django template tags ({{ }}, {% %}), split into:
   - Inline: Small data-passing script with variables
   - External: The actual logic code
3. JS without template tags: Fully extract to external file

Rules:
- Skip email templates (they need inline styles for email clients)
- Don't change JS logic
- Don't break the UI
- If multiple <style> or <script> blocks, merge into one
- CDN/external scripts (with src=) are left as-is
"""

import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_CSS_DIR = os.path.join(BASE_DIR, 'static', 'assets', 'css')
STATIC_JS_DIR = os.path.join(BASE_DIR, 'static', 'assets', 'js')

os.makedirs(STATIC_CSS_DIR, exist_ok=True)
os.makedirs(STATIC_JS_DIR, exist_ok=True)

SKIP_DIRS = ['emails']

def get_asset_name(template_rel_path):
    """Convert template relative path to asset filename."""
    path = template_rel_path.replace('\\', '/').replace('.html', '')
    
    if path.startswith('modules/admin/pages/'):
        name = 'admin-' + path.replace('modules/admin/pages/', '')
    elif path.startswith('modules/cfo/'):
        name = 'cfo-' + path.replace('modules/cfo/', '')
    elif path.startswith('modules/employee/'):
        name = 'employee-' + path.replace('modules/employee/', '')
    elif path.startswith('modules/pm/'):
        name = 'pm-' + path.replace('modules/pm/', '')
    elif path.startswith('shared/layouts/'):
        name = 'shared-' + path.replace('shared/layouts/', '')
    elif path.startswith('shared/sidebars/'):
        name = 'shared-' + path.replace('shared/sidebars/', '')
    elif path.startswith('shared/components/'):
        name = 'shared-' + path.replace('shared/components/', '')
    elif path.startswith('admin_custom/'):
        name = path.replace('admin_custom/', 'admin-custom-').replace('/', '-')
    elif '/' in path:
        name = '-'.join(path.split('/'))
    else:
        name = path
    
    name = name.replace('_', '-').replace('/', '-')
    while '--' in name:
        name = name.replace('--', '-')
    
    return name


def has_django_tags(content):
    """Check if content contains Django template tags."""
    return bool(re.search(r'\{\{.*?\}\}|\{%.*?%\}', content))


def extract_inline_styles(html_content):
    """Extract all inline <style>...</style> blocks."""
    style_pattern = re.compile(r'<style[^>]*>(.*?)</style>', re.DOTALL | re.IGNORECASE)
    css_parts = []
    modified = html_content
    
    matches = list(style_pattern.finditer(html_content))
    for match in reversed(matches):
        css_content = match.group(1).strip()
        if css_content:
            css_parts.insert(0, css_content)
        modified = modified[:match.start()] + modified[match.end():]
    
    return '\n\n'.join(css_parts), modified


def extract_inline_scripts(html_content):
    """Extract inline <script> blocks (not external ones with src=).
    Returns (js_content_list, modified_html) where each js_content is (content, has_django_tags)."""
    script_pattern = re.compile(r'<script(?![^>]*\bsrc\b)[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
    
    js_items = []
    modified = html_content
    
    matches = list(script_pattern.finditer(html_content))
    for match in reversed(matches):
        js_content = match.group(1).strip()
        if js_content:
            has_tags = has_django_tags(js_content)
            js_items.insert(0, (js_content, has_tags))
        modified = modified[:match.start()] + modified[match.end():]
    
    return js_items, modified


def ensure_load_static(html_content):
    """Ensure {% load static %} is present."""
    if '{% load static %}' not in html_content:
        html_content = '{% load static %}\n' + html_content
    return html_content


def add_css_link(html_content, asset_name):
    """Add CSS link in the appropriate place."""
    css_link = "{% static 'assets/css/" + asset_name + ".css' %}"
    link_tag = f'<link rel="stylesheet" href="{css_link}" />'
    
    block_pattern = re.compile(r'({%\s*block\s+extra_css\s*%})', re.IGNORECASE)
    block_match = block_pattern.search(html_content)
    
    if block_match:
        insert_pos = block_match.end()
        html_content = html_content[:insert_pos] + '\n' + link_tag + '\n' + html_content[insert_pos:]
    else:
        head_close = html_content.find('</head>')
        if head_close != -1:
            html_content = html_content[:head_close] + link_tag + '\n' + html_content[head_close:]
    
    return html_content


def add_js_link_and_inline(html_content, asset_name, inline_js=None):
    """Add external JS link and optionally inline JS (for Django template variables)."""
    js_link = "{% static 'assets/js/" + asset_name + ".js' %}"
    script_tag = f'<script src="{js_link}"></script>'
    
    block_pattern = re.compile(r'({%\s*block\s+extra_js\s*%})', re.IGNORECASE)
    block_match = block_pattern.search(html_content)
    
    # Build the insert content: inline data script first, then external script
    parts = []
    if inline_js:
        parts.append(f'<script>\n{inline_js}\n</script>')
    parts.append(script_tag)
    insert_content = '\n'.join(parts)
    
    if block_match:
        insert_pos = block_match.end()
        # Skip any existing <script src="..."> tags (CDN/external)
        remaining = html_content[insert_pos:]
        ext_script_pattern = re.compile(r'\s*<script\s+src=["\'][^"\']*["\'][^>]*>\s*</script>')
        while True:
            ext_match = ext_script_pattern.match(remaining)
            if ext_match:
                insert_pos += ext_match.end()
                remaining = html_content[insert_pos:]
            else:
                break
        
        html_content = html_content[:insert_pos] + '\n' + insert_content + '\n' + html_content[insert_pos:]
    else:
        body_close = html_content.find('</body>')
        if body_close != -1:
            html_content = html_content[:body_close] + insert_content + '\n' + html_content[body_close:]
    
    return html_content


def add_inline_js_only(html_content, inline_js):
    """Add only inline JS (when all JS contains Django template tags)."""
    block_pattern = re.compile(r'({%\s*block\s+extra_js\s*%})', re.IGNORECASE)
    block_match = block_pattern.search(html_content)
    
    insert_content = f'<script>\n{inline_js}\n</script>'
    
    if block_match:
        insert_pos = block_match.end()
        remaining = html_content[insert_pos:]
        ext_script_pattern = re.compile(r'\s*<script\s+src=["\'][^"\']*["\'][^>]*>\s*</script>')
        while True:
            ext_match = ext_script_pattern.match(remaining)
            if ext_match:
                insert_pos += ext_match.end()
                remaining = html_content[insert_pos:]
            else:
                break
        html_content = html_content[:insert_pos] + '\n' + insert_content + '\n' + html_content[insert_pos:]
    else:
        body_close = html_content.find('</body>')
        if body_close != -1:
            html_content = html_content[:body_close] + insert_content + '\n' + html_content[body_close:]
    
    return html_content


def clean_empty_lines(html_content):
    """Clean up excessive empty lines."""
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)
    return html_content


def process_template(template_path, rel_path):
    """Process a single template file."""
    asset_name = get_asset_name(rel_path)
    
    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Extract CSS
    css_content, html_content = extract_inline_styles(html_content)
    
    # Extract JS
    js_items, html_content = extract_inline_scripts(html_content)
    
    if not css_content and not js_items:
        return False, asset_name
    
    has_changes = False
    
    # Ensure {% load static %}
    html_content = ensure_load_static(html_content)
    
    # Write CSS file
    if css_content:
        css_file = os.path.join(STATIC_CSS_DIR, f'{asset_name}.css')
        with open(css_file, 'w', encoding='utf-8') as f:
            f.write(css_content + '\n')
        html_content = add_css_link(html_content, asset_name)
        print(f"  CSS: static/assets/css/{asset_name}.css")
        has_changes = True
    
    # Handle JS
    if js_items:
        # Separate JS with and without Django tags
        pure_js_parts = []
        django_js_parts = []
        
        for content, has_tags in js_items:
            if has_tags:
                django_js_parts.append(content)
            else:
                pure_js_parts.append(content)
        
        if pure_js_parts and not django_js_parts:
            # All JS is pure - extract entirely
            js_file = os.path.join(STATIC_JS_DIR, f'{asset_name}.js')
            with open(js_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(pure_js_parts) + '\n')
            html_content = add_js_link_and_inline(html_content, asset_name)
            print(f"  JS:  static/assets/js/{asset_name}.js")
        elif pure_js_parts and django_js_parts:
            # Mix: extract pure JS, keep Django JS inline
            js_file = os.path.join(STATIC_JS_DIR, f'{asset_name}.js')
            with open(js_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(pure_js_parts) + '\n')
            inline_js = '\n\n'.join(django_js_parts)
            html_content = add_js_link_and_inline(html_content, asset_name, inline_js)
            print(f"  JS:  static/assets/js/{asset_name}.js + inline (Django tags)")
        else:
            # All JS has Django tags - keep inline
            inline_js = '\n\n'.join(django_js_parts)
            html_content = add_inline_js_only(html_content, inline_js)
            print(f"  JS:  kept inline (Django template tags)")
        
        has_changes = True
    
    # Clean up
    html_content = clean_empty_lines(html_content)
    
    # Write modified HTML
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return has_changes, asset_name


def main():
    print("=" * 60)
    print("CSS/JS Extraction from HTML Templates")
    print("=" * 60)
    
    processed = 0
    skipped = 0
    errors = []
    results = []
    
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        rel_root = os.path.relpath(root, TEMPLATES_DIR)
        if any(rel_root.startswith(skip) for skip in SKIP_DIRS):
            continue
        
        for filename in sorted(files):
            if not filename.endswith('.html'):
                continue
            
            template_path = os.path.join(root, filename)
            rel_path = os.path.relpath(template_path, TEMPLATES_DIR)
            
            try:
                print(f"\n[{rel_path}]")
                result, asset_name = process_template(template_path, rel_path)
                if result:
                    processed += 1
                    results.append((rel_path, asset_name))
                else:
                    skipped += 1
                    print(f"  -> No inline CSS/JS found")
            except Exception as e:
                errors.append((rel_path, str(e)))
                print(f"  -> ERROR: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"SUMMARY:")
    print(f"  Processed: {processed} files")
    print(f"  Skipped (no inline CSS/JS): {skipped} files")
    if errors:
        print(f"  Errors: {len(errors)} files")
        for path, err in errors:
            print(f"    - {path}: {err}")
    print("=" * 60)
    
    # List created files
    print("\nCreated CSS files:")
    for f in sorted(os.listdir(STATIC_CSS_DIR)):
        print(f"  static/assets/css/{f}")
    
    print("\nCreated JS files:")
    js_dir_files = os.listdir(STATIC_JS_DIR) if os.path.exists(STATIC_JS_DIR) else []
    for f in sorted(js_dir_files):
        print(f"  static/assets/js/{f}")


if __name__ == '__main__':
    main()
