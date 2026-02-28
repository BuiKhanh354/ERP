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
            # Remove unique constraints first if exists
            try:
                cursor.execute("""
                    SELECT CONSTRAINT_NAME 
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                    WHERE TABLE_NAME = %s AND CONSTRAINT_TYPE = 'UNIQUE'
                    AND CONSTRAINT_NAME LIKE '%%employee%%'
                """, [db_table])
                unique_constraints = cursor.fetchall()
                for (constraint_name,) in unique_constraints:
                    cursor.execute(f"ALTER TABLE [{db_table}] DROP CONSTRAINT [{constraint_name}]")
            except Exception as e:
                print(f"Warning: Could not remove unique constraints: {e}")
            
            # Remove foreign key constraint first if exists
            try:
                cursor.execute("""
                    SELECT CONSTRAINT_NAME 
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                    WHERE TABLE_NAME = %s AND CONSTRAINT_TYPE = 'FOREIGN KEY'
                    AND CONSTRAINT_NAME LIKE '%%employee%%'
                """, [db_table])
                fk_constraints = cursor.fetchall()
                for (constraint_name,) in fk_constraints:
                    cursor.execute(f"ALTER TABLE [{db_table}] DROP CONSTRAINT [{constraint_name}]")
            except Exception as e:
                print(f"Warning: Could not remove foreign key constraints: {e}")
            
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