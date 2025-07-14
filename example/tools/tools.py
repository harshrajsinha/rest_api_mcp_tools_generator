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
# import re
# import pandas as pd
# from pathlib import Path


# from csv import reader
# from io import StringIO

from enum import IntFlag, auto
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
    # parameters: Optional[Dict[str, Parameter]] = field(default_factory=dict)
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


JobType: TypeAlias = Union[
    List[Literal["UI", "ACCELERATION", "INTERNAL", "EXTERNAL"]], str
]
StatusType: TypeAlias = Union[List[Literal["COMPLETED", "CANCELED", "FAILED"]], str]


def _get_class_var_hints(tool: Tools, name: str) -> bool:
    if class_var := get_type_hints(tool, include_extras=True).get(name):
        if cls_args := get_args(class_var):
            if (annot := get_args(cls_args[0])) and len(annot) == 2:
                return annot[-1]


get_for = lambda tool: _get_class_var_hints(tool, "For")
get_project_id_required = lambda tool: _get_class_var_hints(tool, "project_id_required")



def _subclasses(cls):
    for sub in cls.__subclasses__():
        yield from _subclasses(sub)
        yield sub


def get_tools(For: ToolType = None) -> List[Tools]:
    return [
        sc
        for sc in _subclasses(Tools)
        if sc is not Resource
        and not issubclass(sc, Resource)
        
    ]


def get_resources(For: ToolType = None):
    return [
        sc
        for sc in _subclasses(Resource)
        if sc is not Resource 
    ]


class Resource(Tools):
    @property
    def resource_path(self):
        raise NotImplementedError("Subclasses should implement this method")


class Hints(Resource):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SCIKIQ]] = ToolType.FOR_SCIKIQ

    @property
    def resource_path(self):
        return "dremio://hints"

    async def invoke(self) -> Dict[str, str]:
        """Dremio cluster has few key diminsions that can be used to analyze and optimize the cluster.
        Looking at the number of jobs and its statistics and failure rates, and overall system usage
        """
        return self.invoke.__doc__

def system_prompt():
    # For = settings.instance().tools.server_mode
    For = ToolType.FOR_SCIKIQ
    get_tools_prompt = lambda t: "\n\t".join(t.invoke.__doc__.splitlines()) if t.invoke.__doc__ else ""
    all_tools = "\n".join(
        f"{t.__name__}: {get_tools_prompt(t)}"
        for t in (get_tools(For) + get_resources(For))
    )

    return f"""
    You are a helpful AI bot with access to several tools for managing and analyzing the SCIKIQ application, including user, role, and entity management via REST APIs.

    General Instructions:
    - Always require and validate the following parameters for REST API tools: client_key, entity_key, user_key.
    - For tools related to users, roles, or entities, ensure user_role and entity are provided if required.
    - If a user request is missing any mandatory parameter (such as user_role or entity), you must ask the user to provide the missing parameter(s) before proceeding.
    - Prefer to illustrate results using interactive graphical plots where possible.
    - Respond with clear, actionable information and API results.
    - If the user prompt is in a non-English language, translate it to English before processing, but respond in the user's language.
    - Always check your answer before finalizing the result.

    Available Tools:
    {all_tools}

    Notes:
    - Use the appropriate tool for user, role, or entity management tasks.
    - Ensure all required parameters are present in your API calls. If not, prompt the user to provide them.
    """

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
        Convert responsejson output to JSON-RPC 2.0 format.
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

class CreateUserTool(RestApiTool):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SCIKIQ]] = ToolType.FOR_SCIKIQ
    api_path = "/base/user/save"

    def get_parameters(self):
        extra_properties = {
            "first_name": Property(type="string", description="First name of the new user"),
            "last_name": Property(type="string", description="Last name of the new user"),
            "email": Property(type="string", description="Email address of the user"),
            "password": Property(type="string", description="Password for the user"),
            "company": Property(type="string", description="Company name (optional)"),
            "selectEntity": Property(type="array", description="List of entity resource keys (required unless make_clnt_admin=1)"),
            "selectRole": Property(type="array", description="List of roles corresponding to selectEntity (required unless make_clnt_admin=1)"),
            "make_clnt_admin": Property(type="string", description="Set to '1' to make user client admin (optional)"),
        }
        extra_required = ["first_name", "last_name", "email", "password"]
        return RestApiParameters(extra_properties, extra_required)

    async def invoke(
        self,
        first_name,
        last_name,
        email,
        password,
        company=None,
        selectEntity=None,
        selectRole=None,
        make_clnt_admin=None,
        id=None
    ):
        """
        Create a new user in SCIKIQ (Single User Save).

        Required:
        - first_name, last_name, email, password

        Optional:
        - company, selectEntity, selectRole, make_clnt_admin

        If make_clnt_admin is "1", selectEntity and selectRole are not required.
        """
        url = self.get_api_url(self.api_path)
        data = {
            "client_key": self.client_key,
            "entity_key": self.entity_key,
            "user_key": self.user_key,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password,
        }
        if company:
            data["company"] = company
        if make_clnt_admin is not None:
            data["make_clnt_admin"] = make_clnt_admin
        # Only include selectEntity/selectRole if not client admin
        if (not make_clnt_admin or make_clnt_admin == "0"):
            if selectEntity:
                data["selectEntity"] = json.dumps(selectEntity) if isinstance(selectEntity, list) else json.dumps([selectEntity])
            if selectRole:
                data["selectRole"] = json.dumps(selectRole) if isinstance(selectRole, list) else json.dumps([selectRole])

        res = requests.post(url, data=data)
        response = res.json()
        return self.to_jsonrpc(response, id=id)

class ModifyUserTool(RestApiTool):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SCIKIQ]] = ToolType.FOR_SCIKIQ
    api_path = "/base/user/update"

    def get_parameters(self):
        extra_properties = {
            "user_id": Property(type="string", description="ID of the user to modify"),
            "email": Property(type="string", description="New email address (optional)"),
            "password": Property(type="string", description="New password (optional)"),
        }
        extra_required = ["user_id"]
        return RestApiParameters(extra_properties, extra_required)

    async def invoke(self, user_id, email=None, password=None, id=None):
        """
        Modify an existing user in SCIKIQ.
        """
        url = self.get_api_url(self.api_path)
        data = {
            "client_key": self.client_key,
            "entity_key": self.entity_key,
            "user_key": self.user_key,
            "user_id": user_id,
        }
        if email:
            data["email"] = email
        if password:
            data["password"] = password
        res = requests.post(url, data=data)
        response = res.json()
        return self.to_jsonrpc(response, id=id)

class DeleteUserTool(RestApiTool):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SCIKIQ]] = ToolType.FOR_SCIKIQ
    api_path = "/base/user/delete"

    def get_parameters(self):
        extra_properties = {
            "user_id": Property(type="string", description="ID of the user to delete"),
        }
        extra_required = ["user_id"]
        return RestApiParameters(extra_properties, extra_required)

    async def invoke(self, user_id, id=None):
        """
        Delete a user in SCIKIQ.
        """
        url = self.get_api_url(self.api_path)
        data = {
            "client_key": self.client_key,
            "entity_key": self.entity_key,
            "user_key": self.user_key,
            "user_id": user_id,
        }
        res = requests.post(url, data=data)
        response = res.json()
        return self.to_jsonrpc(response, id=id)

class ListUserTool(RestApiTool):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SCIKIQ]] = ToolType.FOR_SCIKIQ
    api_path = "/base/user/list"

    def get_parameters(self):
        # No extra parameters needed for listing users
        return RestApiParameters()

    async def invoke(self, id=None):
        """
        List all users in SCIKIQ.
        """
        url = self.get_api_url(self.api_path)
        data = {
            "client_key": self.client_key,
            "entity_key": self.entity_key,
            "user_key": self.user_key,
        }
        res = requests.post(url, data=data)
        response = res.json()
        return self.to_jsonrpc(response, id=id)

class ListRolesTool(RestApiTool):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SCIKIQ]] = ToolType.FOR_SCIKIQ
    api_path = "/rbac/role/list"

    def get_parameters(self):
        # No extra parameters needed for listing roles
        return RestApiParameters()

    async def invoke(self, id=None):
        """
        List all roles in SCIKIQ.
        """
        url = self.get_api_url(self.api_path)
        data = {
            "client_key": self.client_key,
            "entity_key": self.entity_key,
            "user_key": self.user_key,
        }
        res = requests.post(url, data=data)
        response = res.json()
        return self.to_jsonrpc(response, id=id)

class ListEntitiesTool(RestApiTool):
    For: ClassVar[Annotated[ToolType, ToolType.FOR_SCIKIQ]] = ToolType.FOR_SCIKIQ
    api_path = "/base/entity"

    def get_parameters(self):
        extra_properties = {
        }
        extra_required = []
        return RestApiParameters(extra_properties, extra_required)

    async def invoke(self, user_role, entity, id=None):
        """
        List all entities in SCIKIQ for a given user role and entity.
        """
        url = self.get_api_url(self.api_path)
        data = {
            "client_key": self.client_key,
            "entity_key": self.entity_key,
            "user_key": self.user_key,
            "user_role": user_role,
            "entity": entity,
        }
        res = requests.post(url, data=data)
        response = res.json()
        return self.to_jsonrpc(response, id=id)



