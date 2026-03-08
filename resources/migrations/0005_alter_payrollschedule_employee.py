# Generated manually
from django.db import migrations, models


def remove_employee_field_if_exists(apps, schema_editor):
    """Remove employee field only if it exists."""
    db_table = 'resources_payrollschedule'
    with schema_editor.connection.cursor() as cursor:
        # Check if employee_id column exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = %s AND COLUMN_NAME = 'employee_id'
        """, [db_table])
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            # Remove all constraints related to employee_id
            try:
                cursor.execute("""
                    SELECT CONSTRAINT_NAME 
                    FROM INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE 
                    WHERE TABLE_NAME = %s AND COLUMN_NAME = 'employee_id'
                """, [db_table])
                constraints = cursor.fetchall()
                for (constraint_name,) in constraints:
                    cursor.execute(f"ALTER TABLE [{db_table}] DROP CONSTRAINT [{constraint_name}]")
            except Exception as e:
                print(f"Warning: Could not remove constraints via CONSTRAINT_COLUMN_USAGE: {e}")
                
            # Remove default constraints if any
            try:
                cursor.execute("""
                    SELECT name 
                    FROM sys.default_constraints 
                    WHERE parent_object_id = OBJECT_ID(%s) 
                    AND parent_column_id = (
                        SELECT column_id FROM sys.columns 
                        WHERE object_id = OBJECT_ID(%s) AND name = 'employee_id'
                    )
                """, [db_table, db_table])
                default_constraints = cursor.fetchall()
                for (constraint_name,) in default_constraints:
                    cursor.execute(f"ALTER TABLE [{db_table}] DROP CONSTRAINT [{constraint_name}]")
            except Exception as e:
                print(f"Warning: Could not remove default constraints: {e}")

            # Also check for explicit indexes
            try:
                cursor.execute("""
                    SELECT i.name 
                    FROM sys.indexes i
                    JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                    JOIN sys.columns c ON ic.object_id = c.object_id AND c.column_id = ic.column_id
                    WHERE i.object_id = OBJECT_ID(%s) AND c.name = 'employee_id' AND i.is_primary_key = 0 AND i.is_unique_constraint = 0
                """, [db_table])
                indexes = cursor.fetchall()
                for (idx_name,) in indexes:
                    cursor.execute(f"DROP INDEX [{idx_name}] ON [{db_table}]")
            except Exception as e:
                print(f"Warning: Could not remove index: {e}")
            
            # Remove column
            cursor.execute(f"ALTER TABLE [{db_table}] DROP COLUMN [employee_id]")

def add_is_active_field_if_not_exists(apps, schema_editor):
    """Add is_active field only if it doesn't exist."""
    db_table = 'resources_payrollschedule'
    with schema_editor.connection.cursor() as cursor:
        # Check if is_active column exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = %s AND COLUMN_NAME = 'is_active'
        """, [db_table])
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            # Add column
            cursor.execute(f"ALTER TABLE [{db_table}] ADD [is_active] BIT NOT NULL DEFAULT 1")


def reverse_remove_employee_field(apps, schema_editor):
    """Reverse: Add employee field back (if needed)."""
    # This is a one-way migration, so we don't reverse it
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0004_payrollschedule'),
    ]

    operations = [
        migrations.RunPython(remove_employee_field_if_exists, reverse_remove_employee_field),
        migrations.RunPython(add_is_active_field_if_not_exists, reverse_remove_employee_field),
    ]