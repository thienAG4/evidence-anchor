from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Body JSON dùng camelCase (caseNumber, roleInCase...) như docs/api.md."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
