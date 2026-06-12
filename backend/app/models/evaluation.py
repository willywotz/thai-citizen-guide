"""Golden questions and per-run evaluation scores for agency answer quality."""
from tortoise import fields
from tortoise.models import Model

from app.utils import generate_uuid


class GoldenQuestion(Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    agency = fields.ForeignKeyField("models.Agency", related_name="golden_questions", on_delete=fields.CASCADE)
    question = fields.TextField()
    expected_topics = fields.JSONField(default=list)  # list[str]
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "golden_questions"


class EvalResult(Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    golden_question = fields.ForeignKeyField("models.GoldenQuestion", related_name="results", on_delete=fields.CASCADE)
    score = fields.FloatField()
    answer = fields.TextField(default="")
    judge_reason = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "eval_results"
        ordering = ["-created_at"]
