from typing import Any

from pydantic import BaseModel

class ArtifactLocation(BaseModel):
    def __init__(
        self,
        *,
        uri: str | None = ...,
        uriBaseId: str | None = ...,
        properties: dict[str, Any] | None = ...,
    ) -> None: ...

class Location(BaseModel):
    def __init__(self, *, physicalLocation: PhysicalLocation | None = ..., properties: dict[str, Any] | None = ...) -> None: ...

class Message(BaseModel):
    def __init__(
        self,
        *,
        text: str | None = ...,
        markdown: str | None = ...,
        properties: dict[str, Any] | None = ...,
    ) -> None: ...

class PhysicalLocation(BaseModel):
    def __init__(
        self,
        *,
        artifactLocation: ArtifactLocation | None = ...,
        region: Region | None = ...,
        properties: dict[str, Any] | None = ...,
    ) -> None: ...

class Region(BaseModel):
    def __init__(self, *, startLine: int | None = ..., endLine: int | None = ..., properties: dict[str, Any] | None = ...) -> None: ...

class ReportingConfiguration(BaseModel):
    def __init__(self, *, level: str | None = ..., properties: dict[str, Any] | None = ...) -> None: ...

class ReportingDescriptor(BaseModel):
    id: str

    def __init__(
        self,
        *,
        id: str,
        name: str | None = ...,
        shortDescription: Message | None = ...,
        defaultConfiguration: ReportingConfiguration | None = ...,
        properties: dict[str, Any] | None = ...,
    ) -> None: ...

class Result(BaseModel):
    ruleIndex: int | None

    def __init__(
        self,
        *,
        ruleId: str | None = ...,
        ruleIndex: int | None = ...,
        level: str | None = ...,
        message: Message,
        locations: list[Location] | None = ...,
        partialFingerprints: dict[str, str] | None = ...,
        properties: dict[str, Any] | None = ...,
    ) -> None: ...

class Run(BaseModel):
    def __init__(
        self,
        *,
        tool: Tool,
        results: list[Result] | None = ...,
        automationDetails: dict[str, str] | None = ...,
        originalUriBaseIds: dict[str, ArtifactLocation] | None = ...,
        properties: dict[str, Any] | None = ...,
    ) -> None: ...

class Sarif(BaseModel):
    def __init__(
        self,
        *,
        version: str = ...,
        schema_uri: str | None = ...,
        runs: list[Run],
        properties: dict[str, Any] | None = ...,
    ) -> None: ...

class Tool(BaseModel):
    def __init__(self, *, driver: ToolDriver, properties: dict[str, Any] | None = ...) -> None: ...

class ToolDriver(BaseModel):
    def __init__(
        self,
        *,
        name: str,
        informationUri: str | None = ...,
        rules: list[ReportingDescriptor] | None = ...,
        properties: dict[str, Any] | None = ...,
    ) -> None: ...
