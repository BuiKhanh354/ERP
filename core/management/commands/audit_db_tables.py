from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Audit database tables: missing/extra tables, FK-isolated tables, and write Markdown report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default=r"E:\gitclone\ERP\taskforagent\tester\DB_ISOLATION_REPORT.md",
            help="Output markdown report path.",
        )

    def handle(self, *args, **options):
        out_path = Path(options["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        lines.append("# DB Isolation Report")
        lines.append("")

        try:
            with connection.cursor() as cursor:
                vendor = connection.vendor
                lines.append(f"- DB vendor: `{vendor}`")
                lines.append("")

                # All DB tables (from current schema/user)
                db_tables = set(connection.introspection.table_names(cursor))
                # Managed Django model tables
                model_tables = set()
                for model in apps.get_models():
                    if model._meta.managed:
                        model_tables.add(model._meta.db_table)

                missing_in_db = sorted(t for t in model_tables if t not in db_tables)
                extra_in_db = sorted(t for t in db_tables if t not in model_tables)

                lines.append("## 1) Django Model Coverage")
                lines.append(f"- Model tables (managed): **{len(model_tables)}**")
                lines.append(f"- DB tables (visible): **{len(db_tables)}**")
                lines.append("")

                lines.append("### Missing Tables (model có nhưng DB không có)")
                if missing_in_db:
                    for t in missing_in_db:
                        lines.append(f"- `{t}`")
                else:
                    lines.append("- None")
                lines.append("")

                lines.append("### Extra Tables (DB có nhưng model không quản lý)")
                if extra_in_db:
                    for t in extra_in_db:
                        lines.append(f"- `{t}`")
                else:
                    lines.append("- None")
                lines.append("")

                # FK isolation check (SQL Server-specific query)
                if vendor == "microsoft":
                    fk_sql = """
                    SELECT
                        t.name AS table_name,
                        SUM(CASE WHEN fk.parent_object_id IS NOT NULL THEN 1 ELSE 0 END) AS outgoing_fk,
                        SUM(CASE WHEN fk2.referenced_object_id IS NOT NULL THEN 1 ELSE 0 END) AS incoming_fk
                    FROM sys.tables t
                    LEFT JOIN sys.foreign_keys fk ON fk.parent_object_id = t.object_id
                    LEFT JOIN sys.foreign_keys fk2 ON fk2.referenced_object_id = t.object_id
                    WHERE t.is_ms_shipped = 0
                    GROUP BY t.name
                    ORDER BY t.name
                    """
                    cursor.execute(fk_sql)
                    fk_rows = cursor.fetchall()
                    # rows: (table_name, outgoing_fk, incoming_fk)
                    isolated = []
                    for row in fk_rows:
                        name = str(row[0])
                        outgoing = int(row[1] or 0)
                        incoming = int(row[2] or 0)
                        if outgoing == 0 and incoming == 0:
                            isolated.append(name)

                    lines.append("## 2) FK Isolation")
                    lines.append("Bảng cô lập theo FK = không có FK đi ra và cũng không có FK đi vào.")
                    lines.append("")
                    if isolated:
                        for t in sorted(isolated):
                            lines.append(f"- `{t}`")
                    else:
                        lines.append("- None")
                    lines.append("")
                else:
                    lines.append("## 2) FK Isolation")
                    lines.append(f"- Skip detailed FK audit for vendor `{vendor}`.")
                    lines.append("")

                lines.append("## 3) Raw Summary")
                lines.append(f"- Missing in DB: **{len(missing_in_db)}**")
                lines.append(f"- Extra in DB: **{len(extra_in_db)}**")
                lines.append("")
                lines.append("_Note: Extra tables có thể là bảng legacy, bảng backup, hoặc bảng ngoài Django._")

        except Exception as exc:
            lines.append("## ERROR")
            lines.append(f"- {exc}")
            lines.append("")
            lines.append("Không thể đọc DB tại thời điểm chạy lệnh.")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Report generated: {out_path}"))
