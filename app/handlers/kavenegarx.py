"""Async Kavenegar Python client based on httpx."""

from typing import Optional, Union, List, NamedTuple, NoReturn

import httpx


API_ROOT = httpx.URL('https://api.kavenegar.com/v1/')


# Exceptions
class NotInitialized(Exception):
    """Exception to handle when KavenegarX isn't initialized."""


class UnprocessableResponseError(Exception):
    """Exception to handle when API response couldn't be process."""


class APIError(Exception):
    """Exception to handle API errors."""


# Types
TimeoutTypes = Union[Optional[float], str]


# Schemas
class SendEntryResponse(NamedTuple):
    """Schema model of a single entry in "SendResponse"."""

    messageid: int
    message: str
    status: int
    statustext: str
    sender: str
    receptor: str
    date: float
    cost: int


class SendResponse(NamedTuple):
    """Response schema model of API "Send" action."""

    status: int
    message: str
    entries: List[SendEntryResponse]


class SendArrayResponse(SendResponse):
    """Response schema model of API "SendArray" action."""


class LookupResponse(SendResponse):
    """Response schema model of API "Lookup" action."""


# KavenegarX Module
class KavenegarX():
    """API client module of KavenegarX."""

    initialized = False

    def __init__(
        self,
        api_key: str,
        api_root: Optional[httpx.URL] = API_ROOT,
        client: Optional[httpx.AsyncClient] = None,
        timeout: Optional[int] = None
    ):
        """Pass your init config of Kavenegar."""

        self.initialized = True
        self.api_key = api_key
        self.api_root = api_root
        self.client = client if client else httpx.AsyncClient()
        self.timeout = timeout

    async def aclose(self) -> NoReturn:
        """Async closing and uninitializing method for KavenegarX object."""
        if not self.initialized:
            raise NotInitialized
        await self.client.aclose()
        self.initialized = False

    def _serve_timeout(self, timeout: TimeoutTypes) -> dict:
        timeout = timeout if timeout else self.timeout
        if timeout == 'never':
            return {"timeout": None}
        return {"timeout": timeout} if timeout else {}

    @staticmethod
    def _serve_send(
        receptor: List[str],
        message: str,
        sender: Optional[str] = None,
        date: Optional[float] = None,
        type_msg: Optional[int] = None,
        localid: Optional[List[str]] = None,
        hide: Optional[bool] = None
    ) -> dict:
        receptor = ','.join(receptor)
        data = {'receptor': receptor, 'message': message}
        if sender:
            data['sender'] = sender
        if date:
            data['date'] = date
        if type_msg:
            type_msg = str(type_msg)
            data['type'] = type_msg
        if localid:
            localid = ','.join(localid)
            data['localid'] = localid
        if hide:
            data['hide'] = int(hide)
        return data

    @staticmethod
    def _serve_send_response(response_json: dict) -> SendResponse:
        response = SendResponse(
            **response_json.get('return'),
            entries=list(map(
                lambda response: SendEntryResponse(**response),
                response_json.get('entries')
            ))
        )
        return response

    async def send(
        self,
        receptor: List[str],
        message: str,
        sender: Optional[str] = None,
        date: Optional[float] = None,
        type_msg: Optional[int] = None,
        localid: Optional[List[str]] = None,
        hide: Optional[bool] = None,
        timeout: TimeoutTypes = None
    ) -> SendResponse:
        """Send action of Kavenegar REST API."""
        if not self.initialized:
            raise NotInitialized

        url = httpx.URL(f'{API_ROOT}{self.api_key}/sms/send.json')
        timeout = self._serve_timeout(timeout)

        try:
            request = await self.client.post(
                url,
                data=self._serve_send(
                    receptor,
                    message,
                    sender,
                    date,
                    type_msg,
                    localid,
                    hide
                ),
                **timeout
            )
        except httpx.RequestError as e:
            raise e
        try:
            request.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise APIError(request.json().get('return')) from e
        response_json = request.json()
        try:
            return self._serve_send_response(response_json)
        except Exception as e:
            raise UnprocessableResponseError from e
        finally:
            await self.aclose()
            self.initialized = False

    @staticmethod
    def _serve_lookup(
        receptor: str,
        template: str,
        token: str,
        token2: Optional[str] = None,
        token3: Optional[str] = None,
        token10: Optional[str] = None,
        token20: Optional[str] = None,
        type_msg: Optional[int] = None
    ) -> dict:
        data = {"receptor": receptor, "template": template, "token": token}
        if token2:
            data["token2"] = token2
        if token3:
            data["token3"] = token3
        if token10:
            data["token10"] = token10
        if token20:
            data["token20"] = token20
        if type_msg:
            data["type"] = str(type_msg)
        return data

    @staticmethod
    def _serve_lookup_response(response_json: dict) -> LookupResponse:
        response = LookupResponse(
            **response_json.get('return'),
            entries=list(map(
                lambda response: SendEntryResponse(**response),
                response_json.get('entries')
            ))
        )
        return response

    async def lookup(
        self,
        receptor: str,
        template: str,
        token: str,
        token2: Optional[str] = None,
        token3: Optional[str] = None,
        token10: Optional[str] = None,
        token20: Optional[str] = None,
        type_msg: Optional[int] = None,
        timeout: TimeoutTypes = None
    ) -> LookupResponse:
        if not self.initialized:
            raise NotInitialized

        url = httpx.URL(f'{API_ROOT}{self.api_key}/verify/lookup.json')
        timeout = self._serve_timeout(timeout)

        try:
            request = await self.client.post(
                url,
                data=self._serve_lookup(
                    receptor,
                    template,
                    token,
                    token2,
                    token3,
                    token10,
                    token20,
                    type_msg
                ),
                **timeout
            )
        except httpx.RequestError as e:
            raise e
        try:
            request.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise APIError(request.json().get('return')) from e
        response_json = request.json()
        try:
            return self._serve_lookup_response(response_json)
        except Exception as e:
            raise UnprocessableResponseError from e
