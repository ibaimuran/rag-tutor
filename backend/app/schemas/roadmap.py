from pydantic import BaseModel


class RoadmapNode(BaseModel):
    id: int
    title: str
    status: str
    p_know: int
    prerequisites: list[int] = []
    order: int
    difficulty: int = 1
    chapter_id: int


class ChapterRoadmap(BaseModel):
    id: int
    title: str
    knowledge_points: list[dict]
    chapter_progress: int


class RoadmapData(BaseModel):
    course_title: str
    course_id: int
    overall_progress: int
    chapters: list[dict]
