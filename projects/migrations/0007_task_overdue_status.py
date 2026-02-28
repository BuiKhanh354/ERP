from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0006_task_started_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="task",
            name="status",
            field=models.CharField(
                choices=[
                    ("todo", "To Do"),
                    ("in_progress", "In Progress"),
                    ("review", "Review"),
                    ("done", "Done"),
                    ("overdue", "Overdue"),
                ],
                default="todo",
                max_length=20,
            ),
        ),
    ]

