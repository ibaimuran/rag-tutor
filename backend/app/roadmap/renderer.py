from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from ..config import settings


class RoadmapRenderer:
    def __init__(self):
        template_dir = Path(settings.template_dir)
        if not template_dir.exists():
            template_dir = Path(__file__).parent.parent.parent.parent / "frontend" / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def render_roadmap(self, roadmap_data: dict) -> str:
        template = self.env.get_template("roadmap_page.html")
        return template.render(**roadmap_data)

    def render_roadmap_component(self, roadmap_data: dict) -> str:
        template = self.env.get_template("components/roadmap_node.html")
        result = ""
        for ch in roadmap_data.get("chapters", []):
            for kp in ch.get("knowledge_points", []):
                result += template.render(
                    id=kp["id"],
                    title=kp["title"],
                    status=kp["status"],
                    p_know=kp["p_know"],
                    difficulty=kp.get("difficulty", 1),
                )
        return result
