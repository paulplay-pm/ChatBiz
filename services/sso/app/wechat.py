"""V6a SSO service: 企微 OAuth2 联调(V0 阶段).

exchange_code: POST 企微 /sns/oauth2/access_token 用 code 换 access_token + openid
fetch_userinfo: POST /sns/userinfo 拉 userinfo(name / email)
4 错误边界:WorkflowRuntimeError (企微 5xx) / UserError (参数缺失)
"""
from __future__ import annotations

import logging

import httpx

from .jwt_utils import (
    UserError,
    WorkflowRuntimeError,
)

logger = logging.getLogger(__name__)

# 企微 OAuth2 端点
WECHAT_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"

DEFAULT_TIMEOUT = 5.0


class WeChatClient:
    """V6a V0 企微扫码后端联调。"""

    def __init__(self, corp_id: str, agent_id: str, corp_secret: str, redirect_uri: str):
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.corp_secret = corp_secret
        self.redirect_uri = redirect_uri

    @property
    def _available(self) -> bool:
        return bool(self.corp_id and self.agent_id and self.corp_secret)

    def get_authorize_url(self, state: str) -> str:
        """构造企微 authorize URL(scope=snsapi_login, V6a V0)。"""
        return (
            "https://open.weixin.qq.com/connect/oauth2/authorize"
            f"?appid={self.corp_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&response_type=code"
            "&scope=snsapi_login"
            f"&state={state}"
            f"&agentid={self.agent_id}"
        )

    async def exchange_code(self, code: str) -> tuple[str, str]:
        """code → (access_token, openid)。"""
        if not self._available:
            raise WorkflowRuntimeError(
                "企微 corpId/agentId/secret 未配置",
                "runtime.wechat_unavailable",
            )
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                r = await client.get(
                    WECHAT_ACCESS_TOKEN_URL,
                    params={
                        "appid": self.corp_id,
                        "secret": self.corp_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                    },
                )
            data = r.json()
        except httpx.TimeoutException as e:
            raise WorkflowRuntimeError(
                f"企微 access_token timeout: {e}", "runtime.wechat_timeout"
            ) from e
        except httpx.HTTPError as e:
            raise WorkflowRuntimeError(
                f"企微 access_token HTTP error: {e}", "runtime.wechat_5xx"
            ) from e

        if "errcode" in data and data["errcode"] != 0:
            errcode = data.get("errcode")
            errmsg = data.get("errmsg", "unknown")
            # 40029: invalid code; 40163: code been used
            if errcode in (40029, 40163):
                raise UserError(
                    f"企微 code 无效或已使用: {errmsg}", "user.wechat_invalid_code"
                )
            raise WorkflowRuntimeError(
                f"企微 access_token 错误 {errcode}: {errmsg}", "runtime.wechat_5xx"
            )

        access_token = data.get("access_token")
        openid = data.get("openid")
        if not access_token or not openid:
            raise WorkflowRuntimeError(
                "企微 access_token 响应缺字段", "runtime.wechat_5xx"
            )
        return access_token, openid

    async def fetch_userinfo(
        self, access_token: str, openid: str
    ) -> dict[str, str]:
        """access_token + openid → {openid, nickname, headimgurl, ...}。

        企微 snsapi_login scope 实际返 unionid 字段(若配置);V6a 取 nickname 当 name。
        """
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                r = await client.get(
                    WECHAT_USERINFO_URL,
                    params={"access_token": access_token, "openid": openid, "lang": "zh_CN"},
                )
            data = r.json()
        except (httpx.TimeoutException, httpx.HTTPError) as e:
            raise WorkflowRuntimeError(
                f"企微 userinfo 调用失败: {e}", "runtime.wechat_5xx"
            ) from e

        if "errcode" in data and data["errcode"] != 0:
            raise WorkflowRuntimeError(
                f"企微 userinfo 错误: {data}", "runtime.wechat_5xx"
            )
        return {
            "openid": data.get("openid", openid),
            "name": data.get("nickname", ""),
            "avatar": data.get("headimgurl", ""),
        }
