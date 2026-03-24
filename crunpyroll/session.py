import base64
import re
import traceback
from datetime import datetime, timedelta
from .utils import (
    PUBLIC_TOKEN, get_date,get_api_headers,USER_AGENT
)

from .errors import ClientNotAuthorized

from typing import Optional

import crunpyroll

class Session:
    def __init__(
        self,
        client: "crunpyroll.Client"
    ):
        self._client: crunpyroll.Client = client

        self.access_token: str = None
        self.refresh_token: str = None
        self.expiration: datetime = None

    @property
    def is_authorized(self):
        return bool(self.access_token and self.refresh_token)
    
    @property
    def authorization_header(self):
        return {"Authorization": f"Bearer {self.access_token}",
                "User-Agent": USER_AGENT,
                "Cookie":f'etp_rt={self.refresh_token}'}
    
    async def retrieve(self) -> None:
        if not self.is_authorized:
            raise ClientNotAuthorized("Client is not authorized yet.")
        date = get_date()
        if date >= self.expiration:
            await self.refresh()

    async def get_public_token(self) -> Optional[str]:
        
        return PUBLIC_TOKEN
        
        # 1. 修正API地址拼写错误
        # api_url = "https://static.crunchyroll.com/vilos-v2/web/vilos/js/bundle.js"

        # try:
        #     # 2. 更明确的HTTP客户端调用
        #     response = await self._client.http.get(
        #         url=api_url,
        #         headers=get_api_headers(headers=None)
        #     )
        #     response.raise_for_status()  # 自动处理非200状态码

        #     # 3. 确保获取文本内容（部分库需要 await response.text()）
        #     raw_js = response.text

        #     # 4. 修正正则表达式（移除多余斜杠）
        #     token_pattern = r'prod="([\w-]+:[\w-]+)"'
        #     token_match = re.search(token_pattern, raw_js)

        #     if not token_match:
        #         return None
        #     # 5. 更安全的编码处理
        #     raw_token = token_match.group(1)
        #     latin1_bytes = raw_token.encode("latin1")
        #     base64_token = base64.b64encode(latin1_bytes).decode("utf-8")

        #     return base64_token
        # except Exception as e:
        #     # 6. 添加错误日志
        #     print(f"Failed to get production token: {traceback.format_exc()}")
        #     return None

    
    async def authorize(self) -> Optional[bool]:
        response = await self._client.api_request(
            method="POST",
            endpoint="auth/v1/token",
            headers={
                "Authorization": f"Basic {PUBLIC_TOKEN}",
                "User-Agent": USER_AGENT,
                "Connection": "Keep-Alive",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            },
            payload={
                "username": self._client.email,
                "password": self._client.password,
                "grant_type": "password",
                "scope": "offline_access",
                "device_id": self._client.device_id,
                "device_name": self._client.device_name,
                "device_type": self._client.device_type
            },
            include_session=False,
            allow_refresh_on_401=False

        )
        self.access_token = response.get("access_token")
        self.refresh_token = response.get("refresh_token")
        self.expiration = get_date() + timedelta(
            seconds=response.get("expires_in")
        )
        return True
    
    async def refresh(self) -> Optional[bool]:
        response = await self._client.api_request(
            method="POST",
            endpoint="auth/v1/token",
            headers={
                "Authorization": f"Basic {PUBLIC_TOKEN}"
            },
            payload={
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
                "scope": "offline_access",
                "device_id": self._client.device_id,
                "device_name": self._client.device_name,
                "device_type": self._client.device_type
            },
            include_session=False,
            allow_refresh_on_401=False
        )
        self.access_token = response.get("access_token")
        self.refresh_token = response.get("refresh_token")
        self.expiration = get_date() + timedelta(
            seconds=response.get("expires_in")
        )
        return True
