import asyncio
import json
import pytest
import sys

from eth_utils import (
    to_bytes,
)

from web3.exceptions import (
    TimeExhausted,
)
from web3.providers.websocket import (
    WebsocketProviderV2,
)
from web3.types import (
    RPCEndpoint,
)


def _mock_ws(provider):
    # move to top of file when python 3.7 is no longer supported in web3.py
    from unittest.mock import (
        AsyncMock,
    )

    provider._ws = AsyncMock()


@pytest.mark.asyncio
@pytest.mark.skipif(
    # TODO: remove when python 3.7 is no longer supported in web3.py
    #  python 3.7 is already sunset so this feels like a reasonable tradeoff
    sys.version_info < (3, 8),
    reason="Uses AsyncMock, not supported by python 3.7",
)
async def test_async_make_request_caches_all_undesired_responses_and_returns_desired():
    provider = WebsocketProviderV2("ws://mocked")

    method_under_test = provider.make_request

    _mock_ws(provider)
    undesired_responses_count = 10
    ws_recv_responses = [
        to_bytes(
            text=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "eth_subscription",
                    "params": {"subscription": "0x1", "result": f"0x{i}"},
                }
            )
        )
        for i in range(0, undesired_responses_count)
    ]
    # The first request we make should have an id of `0`, expect the response to match
    # that id. Append it as the last response in the list.
    ws_recv_responses.append(b'{"jsonrpc": "2.0", "id":0, "result": "0x1337"}')
    provider._ws.recv.side_effect = ws_recv_responses

    response = await method_under_test(RPCEndpoint("some_method"), ["desired_params"])
    assert response == json.loads(ws_recv_responses.pop())  # pop the expected response

    assert (
        len(provider._request_processor._subscription_response_deque)
        == len(ws_recv_responses)
        == undesired_responses_count
    )

    for cached_response in provider._request_processor._subscription_response_deque:
        # assert all cached responses are in the list of responses we received
        assert to_bytes(text=json.dumps(cached_response)) in ws_recv_responses


@pytest.mark.asyncio
@pytest.mark.skipif(
    # TODO: remove when python 3.7 is no longer supported in web3.py
    #  python 3.7 is already sunset so this feels like a reasonable tradeoff
    sys.version_info < (3, 8),
    reason="Uses AsyncMock, not supported by python 3.7",
)
async def test_async_make_request_returns_cached_response_with_no_recv_if_cached():
    provider = WebsocketProviderV2("ws://mocked")

    method_under_test = provider.make_request

    _mock_ws(provider)

    # cache the response, so we should get it immediately & should never call `recv()`
    desired_response = {"jsonrpc": "2.0", "id": 0, "result": "0x1337"}
    provider._request_processor.cache_raw_response(desired_response)

    response = await method_under_test(RPCEndpoint("some_method"), ["desired_params"])
    assert response == desired_response

    assert len(provider._request_processor._request_response_cache) == 0
    assert not provider._ws.recv.called  # type: ignore


@pytest.mark.asyncio
@pytest.mark.skipif(
    # TODO: remove when python 3.7 is no longer supported in web3.py
    #  python 3.7 is already sunset so this feels like a reasonable tradeoff
    sys.version_info < (3, 8),
    reason="Uses AsyncMock, not supported by python 3.7",
)
async def test_async_make_request_times_out_of_while_loop_looking_for_response():
    timeout = 0.001
    provider = WebsocketProviderV2("ws://mocked", request_timeout=timeout)

    method_under_test = provider.make_request

    _mock_ws(provider)
    # mock the websocket to never receive a response & sleep longer than the timeout
    provider._ws.recv = lambda *args, **kwargs: asyncio.sleep(1)

    with pytest.raises(
        TimeExhausted,
        match=r"Timed out waiting for response with request id `0` after "
        rf"{timeout} second\(s\)",
    ):
        await method_under_test(RPCEndpoint("some_method"), ["desired_params"])
