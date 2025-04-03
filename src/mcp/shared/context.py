from dataclasses import dataclass
from typing import Any, Generic

from typing_extensions import TypeVar

from mcp.shared.session import BaseSession
from mcp.types import RequestId, RequestParams

SessionT = TypeVar("SessionT", bound=BaseSession[Any, Any, Any, Any, Any])
LifespanContextT = TypeVar("LifespanContextT")


@dataclass
class RequestContext(Generic[SessionT, LifespanContextT]):
    request_id: RequestId
    meta: RequestParams.Meta | None
    session: SessionT
    lifespan_context: LifespanContextT

    @property
    def client_id(self) -> str | None:
        """Get the client ID if available."""
        if hasattr(self.session, "client_id"):
            return self.session.client_id
        return None
        
    @property
    def client_request_count(self) -> int:
        """Get the number of requests from this client."""
        if hasattr(self.session, "client_request_count"):
            return self.session.client_request_count
        return 0