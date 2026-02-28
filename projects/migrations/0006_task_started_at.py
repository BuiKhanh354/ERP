from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0005_task_assignment_status_task_department_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="started_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Thời điểm bắt đầu tính giờ ước tính",
                null=True,
            ),
        ),
    ]

