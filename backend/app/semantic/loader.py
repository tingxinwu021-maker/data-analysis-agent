"""加载并校验语义层定义（semantic/semantic.yaml）。"""
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# 项目根目录下的 semantic/ 目录
SEMANTIC_FILE = Path(__file__).resolve().parents[3] / "semantic" / "semantic.yaml"


class Column(BaseModel):
    name: str
    type: str = "varchar"
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)


class Model(BaseModel):
    name: str
    description: str = ""
    columns: list[Column] = Field(default_factory=list)


class Metric(BaseModel):
    name: str
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)
    entity: str = ""
    expression: str | None = None


class Example(BaseModel):
    question: str
    sql: str


class SemanticLayer(BaseModel):
    version: int = 1
    models: list[Model] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)


def load_semantic_layer() -> SemanticLayer:
    """读取 semantic.yaml 并解析为类型化对象（含校验）。"""
    data = yaml.safe_load(SEMANTIC_FILE.read_text(encoding="utf-8"))
    return SemanticLayer(**data)


def find_metric(sl: SemanticLayer, name: str) -> Metric | None:
    for m in sl.metrics:
        if m.name == name:
            return m
    return None
