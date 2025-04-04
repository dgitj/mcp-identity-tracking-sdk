import anyio
import pytest

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.session import ServerSession
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.shared.session import RequestResponder
from mcp.types import (
    ClientNotification,
    InitializedNotification,
    JSONRPCMessage,
    PromptsCapability,
    ResourcesCapability,
    ServerCapabilities,
    TextContent,
)


@pytest.mark.anyio
async def test_server_session_initialize():
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream[
        JSONRPCMessage
    ](1)
    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream[
        JSONRPCMessage
    ](1)

    # Create a message handler to catch exceptions
    async def message_handler(
        message: RequestResponder[types.ServerRequest, types.ClientResult]
        | types.ServerNotification
        | Exception,
    ) -> None:
        if isinstance(message, Exception):
            raise message

    received_initialized = False

    async def run_server():
        nonlocal received_initialized

        async with ServerSession(
            client_to_server_receive,
            server_to_client_send,
            InitializationOptions(
                server_name="mcp",
                server_version="0.1.0",
                capabilities=ServerCapabilities(),
            ),
        ) as server_session:
            async for message in server_session.incoming_messages:
                if isinstance(message, Exception):
                    raise message

                if isinstance(message, ClientNotification) and isinstance(
                    message.root, InitializedNotification
                ):
                    received_initialized = True
                    return

    try:
        async with (
            ClientSession(
                server_to_client_receive,
                client_to_server_send,
                message_handler=message_handler,
            ) as client_session,
            anyio.create_task_group() as tg,
        ):
            tg.start_soon(run_server)

            await client_session.initialize()
    except anyio.ClosedResourceError:
        pass

    assert received_initialized


@pytest.mark.anyio
async def test_server_capabilities():
    server = Server("test")
    notification_options = NotificationOptions()
    experimental_capabilities = {}

    # Initially no capabilities
    caps = server.get_capabilities(notification_options, experimental_capabilities)
    assert caps.prompts is None
    assert caps.resources is None

    # Add a prompts handler
    @server.list_prompts()
    async def list_prompts():
        return []

    caps = server.get_capabilities(notification_options, experimental_capabilities)
    assert caps.prompts == PromptsCapability(listChanged=False)
    assert caps.resources is None

    # Add a resources handler
    @server.list_resources()
    async def list_resources():
        return []

    caps = server.get_capabilities(notification_options, experimental_capabilities)
    assert caps.prompts == PromptsCapability(listChanged=False)
    assert caps.resources == ResourcesCapability(subscribe=False, listChanged=False)

@pytest.mark.anyio
async def test_client_identity_tracking():
    """Test that client identity is properly tracked."""
    server = Server("identity_test")

    # Define a simple tool that uses client identity
    @server.call_tool()
    async def identity_tool(name: str, arguments: dict | None) -> list:
        ctx = server.request_context
        client_id = ctx.client_id
        request_count = ctx.client_request_count
        return [
            TextContent(
                type="text", text=f"Hello {client_id}, this is request #{request_count}"
            )
        ]

    async with create_connected_server_and_client_session(server) as session:
        # First request
        result1 = await session.call_tool("identity_tool", {})
        assert "Hello mcp, this is request #1" in result1.content[0].text

        # Second request
        result2 = await session.call_tool("identity_tool", {})
        assert "Hello mcp, this is request #2" in result2.content[0].text