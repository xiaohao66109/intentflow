"""Project-scoped learning journals, kept separate from engineering evidence."""
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from intentflow_core.models import Project, LearningNote, serialize, now

Stage = Literal['project-context', 'problem-evidence', 'specification', 'engineering-intent',
                'software-change', 'verification', 'runtime-outcome', 'next-change']

class NoteContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    attempt: str = Field(default='', max_length=10000)
    evidence: str = Field(default='', max_length=10000)
    reflection: str = Field(default='', max_length=10000)
    checked: list[str] = Field(default_factory=list, max_length=20)
    assessment: 'GradeAttempt | None' = None
    attempts: list['GradeAttempt'] = Field(default_factory=list, max_length=20)

class GradeDimension(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(max_length=100)
    score: int = Field(ge=0, le=25)
    comment: str = Field(max_length=1000)

class QuestionGrade(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Literal['attempt', 'evidence', 'reflection']
    title: str = Field(max_length=200)
    score: int = Field(ge=0, le=35)
    maximum: int = Field(ge=1, le=35)
    status: Literal['达到要求', '需要补充']
    comment: str = Field(max_length=1000)

class GradeAttempt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    score: int = Field(ge=0, le=100)
    level: str = Field(max_length=100)
    questions: list[QuestionGrade] = Field(default_factory=list, max_length=3)
    dimensions: list[GradeDimension] = Field(max_length=10)
    next: str = Field(max_length=2000)
    sourceHint: str = Field(max_length=2000)
    referencePoints: list[str] = Field(max_length=20)
    signature: str = Field(max_length=20000)
    submittedAt: str = Field(max_length=100)
    number: int = Field(ge=1, le=1000)

NoteContent.model_rebuild()

class NoteInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
    content: NoteContent

def install_learning(app, factory):
    router = APIRouter(prefix='/api/projects/{pid}/learning')

    def content(body: NoteInput):
        value = body.content.model_dump()
        if value['assessment'] is None:
            value.pop('assessment')
        elif not value['assessment']['questions']:
            value['assessment'].pop('questions')
        if not value['attempts']:
            value.pop('attempts')
        else:
            for attempt in value['attempts']:
                if not attempt['questions']:
                    attempt.pop('questions')
        return value

    def project(s, pid):
        if s.get(Project, pid) is None:
            raise HTTPException(404, '项目不存在')

    @router.get('')
    def read(pid: str):
        with factory.begin() as s:
            project(s, pid)
            return [serialize(n) for n in s.scalars(select(LearningNote).where(LearningNote.project_id == pid))]

    @router.put('/{stage}')
    def save(pid: str, stage: Stage, body: NoteInput):
        try:
            with factory.begin() as s:
                project(s, pid)
                if body.revision == 0:
                    item = LearningNote(project_id=pid, stage=stage, content=content(body))
                    s.add(item)
                    s.flush()
                else:
                    result = s.execute(update(LearningNote).where(
                        LearningNote.project_id == pid, LearningNote.stage == stage,
                        LearningNote.revision == body.revision).values(
                            content=content(body), revision=body.revision + 1, updated_at=now()))
                    if result.rowcount != 1:
                        raise HTTPException(409, '学习记录已在另一页面更新。请先复制当前填写内容，再重新加载后合并。')
                    item = s.get(LearningNote, (pid, stage))
                return serialize(item)
        except IntegrityError:
            raise HTTPException(409, '学习记录已在另一页面创建。请先复制当前填写内容，再重新加载后合并。') from None

    app.include_router(router)
