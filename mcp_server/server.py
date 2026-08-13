import os

from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp_server.services.data_service import (
    get_latest_data as get_latest_data_service,
    get_statistics as get_statistics_service,
    search_data as search_data_service,
)

load_dotenv()

MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN")
if not MCP_AUTH_TOKEN:
    raise RuntimeError("MCP_AUTH_TOKEN is required")


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            authorization = Headers(scope=scope).get("authorization")
            if authorization != f"Bearer {self.token}":
                response = JSONResponse(
                    {"error": "unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


mcp = MCPServer("YBIGTA Review Data")


@mcp.tool()
def get_latest_data(limit: int = 10) -> list[dict]:
    """가장 최근에 수집된 리뷰를 조회한다."""
    return get_latest_data_service(limit=limit)


@mcp.tool()
def search_data(
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """키워드와 기간으로 리뷰를 검색한다."""
    return search_data_service(
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


@mcp.tool()
def get_statistics(column: str = "rating") -> dict:
    """리뷰 별점의 평균, 최솟값, 최댓값, 개수를 조회한다."""
    return get_statistics_service(column=column)


mcp_app = mcp.streamable_http_app(
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    )
)
app = BearerAuthMiddleware(mcp_app, MCP_AUTH_TOKEN)
