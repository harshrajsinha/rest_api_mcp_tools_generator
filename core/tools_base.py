"""
Base tools structure - equivalent to the example tools.py but as a Django module
"""
from typing import (
    List,
    Dict,
    Any,
    Optional,
    Literal,
    TypeAlias,
    Union,
    Annotated,
    ClassVar,
    get_args,
    get_type_hints,
)

from dataclasses import dataclass, asdict, field
from enum import auto, IntFlag
import requests
import json


class ToolType(IntFlag):
    FOR_SELF = auto()  # For tools that are self-contained and do not require external resources
    FOR_SCIKIQ = auto()  # For CRUD operations on SCIKIQ resources like users, roles, entities
    FOR_PROMETHEUS = (
        auto()
    )  # supporting any prometheus stack setup to in conjuction with dremio
    FOR_DATA_PATTERNS = (
        auto()
    )  # discovering data patterns analysis within your data using dremio's semantic layer
    EXPERIMENTAL = (
        auto()
    )  # any experimental tools that are not yet ready for production


@dataclass
class Property:
    type: Optional[str] = "string"
    description: Optional[str] = ""


@dataclass
class Parameters:
    type: Optional[str] = "object"
    properties: Optional[Dict[str, Property]] = field(default_factory=dict)
    required: Optional[List[str]] = field(default_factory=list)


@dataclass
class Function:
    name: str
    description: str
    parameters: Parameters


@dataclass
class Tool:
    """
    A wrapper for integrating the same tool with LangChain based tool calling agents.
    """

    type: Optional[str] = "function"
    function: Optional[Function] = None

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not self.function.parameters.properties:
            del d["function"]["parameters"]
        return d


class Tools:
    """
    Base class for all tools. For REST API tools, inherit from RestApiTool.
    """
    def __init__(self, **kwargs):
        # Accepts arbitrary keyword arguments for flexibility in subclasses
        pass

    async def invoke(self, **kwargs):
        raise NotImplementedError("Subclasses should implement this method")

    def get_parameters(self):
        return Parameters()

    # support for LangChain tools as compatibility
    def as_tool(self):
        return Tool(
            function=Function(
                name=self.__class__.__name__,
                description=self.invoke.__doc__,
                parameters=self.get_parameters(),
            )
        )


@dataclass
class RestApiParameters(Parameters):
    
    def __init__(self, extra_properties=None, extra_required=None):
        base_properties = {
            "client_key": Property(type="string", description="Client key"),
            "entity_key": Property(type="string", description="Entity key"),
            "user_key": Property(type="string", description="User key"),
        }
        if extra_properties:
            base_properties.update(extra_properties)
        base_required = ["client_key", "entity_key", "user_key"]
        if extra_required:
            base_required += extra_required
        super().__init__(properties=base_properties, required=base_required)


class RestApiTool(Tools):
    """
    Base class for REST API tools. All REST API tools should inherit from this.
    Provides common parameters: client_key, entity_key, user_key.
    """

    api_base_url: str = "http://localhost:9000"  # Default, can be overridden or set from config

    For: ClassVar[Annotated[ToolType, ToolType.FOR_SELF]] = ToolType.FOR_SELF

    def __init__(self, config=None, **kwargs):
        """
        Accepts a config object (e.g., SciKiqConfig) to set base_url, client_key, entity_key, user_key.
        """
        super().__init__(**kwargs)
        self.config = config
        if config:
            self.api_base_url = getattr(config, "base_url", self.api_base_url)
            self.client_key = getattr(config, "client_key", None)
            self.entity_key = getattr(config, "entity_key", None)
            self.user_key = getattr(config, "user_key", None)
        else:
            self.client_key = None
            self.entity_key = None
            self.user_key = None

    def get_parameters(self):
        # Subclasses can override and provide extra_properties and extra_required
        return RestApiParameters()

    def get_api_url(self, path: str) -> str:
        return f"{self.api_base_url}{path}"

    def get_default_param(self, name, value):
        # Use value if provided, else use from config if available
        if value is not None:
            return value
        return getattr(self, name, None)

    def to_jsonrpc(self, response, id=None):
        """
        Convert response json output to JSON-RPC 2.0 format.
        """
        jsonrpc = "2.0"
        # If id is not provided, use -1 as default
        if id is None:
            id = response.get("request_id", -1)
        if not response.get("error", False):
            # Success
            return {
                "jsonrpc": jsonrpc,
                "result": {
                    "msg": response.get("msg", ""),
                    "data": response.get("data", []),
                    "status": response.get("status", 200),
                    "type": response.get("type", "json"),
                    "total_count": response.get("total_count", -1),
                },
                "id": id,
            }
        else:
            # Error
            return {
                "jsonrpc": jsonrpc,
                "error": {
                    "code": response.get("status", 500),
                    "message": response.get("msg", "Internal Server Error"),
                    "data": response.get("data", []),
                },
                "id": id,
            }

    async def invoke(self, **kwargs):
        raise NotImplementedError("Subclasses should implement this method")


def _subclasses(cls):
    """Get all subclasses of a class recursively"""
    for sub in cls.__subclasses__():
        yield from _subclasses(sub)
        yield sub


def get_tools(For: ToolType = None) -> List[Tools]:
    """Get all tool classes"""
    return [
        sc
        for sc in _subclasses(Tools)
        if not issubclass(sc, RestApiTool) or sc is RestApiTool
    ]


def get_rest_api_tools(For: ToolType = None) -> List[RestApiTool]:
    """Get all REST API tool classes"""
    return [
        sc
        for sc in _subclasses(RestApiTool)
        if sc is not RestApiTool
    ]
