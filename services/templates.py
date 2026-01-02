# services/templates.py
from pathlib import Path

class TemplateManager:
    def __init__(self, template_dir: Path):
        self.template_dir = Path(template_dir)

    def _normalize(self, name: str) -> str:
        """
        Accept:
          - "6300m-standard"
          - "6300m-standard.j2"
        and normalize to: "6300m-standard"
        """
        name = (name or "").strip()
        if name.lower().endswith(".j2"):
            name = name[:-3]
        return name

    def list_templates(self):
        # Return keys without extension
        return sorted([p.stem for p in self.template_dir.glob("*.j2")])

    def load_template(self, name: str) -> str:
        key = self._normalize(name)
        path = self.template_dir / f"{key}.j2"

        if not path.exists():
            available = ", ".join(self.list_templates())
            raise FileNotFoundError(
                f"Template not found: {path} (available: {available})"
            )

        return path.read_text(encoding="utf-8")
