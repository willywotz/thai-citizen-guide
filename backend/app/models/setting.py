from tortoise import fields
from tortoise.models import Model


class Setting(Model):
    key = fields.CharField(max_length=100, primary_key=True)
    value = fields.TextField()
    field_type = fields.CharField(max_length=20, default="str")
    group = fields.CharField(max_length=50)
    is_secret = fields.BooleanField(default=False)
    updated_at = fields.DatetimeField(auto_now=True)
    updated_by = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "settings"