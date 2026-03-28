# -*- coding: utf8 -*-
import concurrent.futures
import json
import math
import os
import random
import time
import traceback
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from util.aes_help import decrypt_data, encrypt_data
import util.push_util as push_util
import util.zepp_helper as zepp_helper
from util.time_util import format_now, get_time_ms


CONFIG_FILE = "config.json"
TOKEN_DATA_FILE = "encrypted_tokens.data"


class ConfigError(ValueError):
    """配置校验异常。"""


@dataclass(frozen=True)
class AccountCredential:
    """单个账号的登录信息。"""

    user: str
    password: str


@dataclass(frozen=True)
class AppConfig:
    """运行所需的全部配置。"""

    accounts: list[AccountCredential]
    min_step: int
    max_step: int
    sleep_gap: float
    use_concurrent: bool
    push_config: push_util.PushConfig


@dataclass
class TokenStore:
    """本地 token 缓存。"""

    aes_key: bytes | None = None
    data_path: str = TOKEN_DATA_FILE
    tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    load_error: str | None = None
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @property
    def enabled(self) -> bool:
        return self.aes_key is not None

    def load(self) -> None:
        if not self.enabled or not os.path.exists(self.data_path):
            return

        try:
            with open(self.data_path, "rb") as file:
                encrypted_data = file.read()
            decrypted_data = decrypt_data(encrypted_data, self.aes_key, None)
            loaded_tokens = json.loads(decrypted_data.decode("utf-8"))
            if isinstance(loaded_tokens, dict):
                self.tokens = loaded_tokens
            else:
                raise ValueError("缓存文件内容不是对象结构")
        except Exception as exc:
            self.tokens = {}
            self.load_error = f"密钥不正确或者加密内容损坏，已放弃读取缓存 token：{exc}"

    def get(self, user: str) -> dict[str, Any] | None:
        with self._lock:
            token_info = self.tokens.get(user)
            return dict(token_info) if token_info is not None else None

    def set(self, user: str, token_info: dict[str, Any]) -> None:
        with self._lock:
            self.tokens[user] = dict(token_info)

    def persist(self) -> None:
        if not self.enabled:
            return

        with self._lock:
            origin_str = json.dumps(self.tokens, ensure_ascii=False)
        cipher_data = encrypt_data(origin_str.encode("utf-8"), self.aes_key, None)
        with open(self.data_path, "wb") as file:
            file.write(cipher_data)


def load_config_dict(config_path: str = CONFIG_FILE) -> dict[str, Any]:
    """读取本地 JSON 配置文件。"""
    if not os.path.exists(config_path):
        raise ConfigError(f"未找到配置文件 {config_path}，请先复制 config.example.json 并填写配置。")

    if os.path.getsize(config_path) == 0:
        raise ConfigError(f"配置文件 {config_path} 为空，请先填写配置。")

    try:
        with open(config_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{config_path} 不是合法的 JSON：{exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"{config_path} 顶层必须是 JSON 对象。")
    return data


def normalize_user_name(user: str) -> str:
    """标准化用户名，手机号补齐 +86。"""
    user = user.strip()
    if not user:
        raise ConfigError("账号不能为空。")
    if user.startswith("+86") or "@" in user:
        return user
    return f"+86{user}"


def desensitize_user_name(user: str) -> str:
    """对用户名进行脱敏。"""
    if len(user) <= 8:
        left_length = max(math.floor(len(user) / 3), 1)
        return f"{user[:left_length]}***{user[-left_length:]}"
    return f"{user[:3]}****{user[-4:]}"


def parse_int(value: Any, field_name: str, default: int, minimum: int | None = None) -> int:
    """解析整数配置。"""
    if value in (None, ""):
        result = default
    else:
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{field_name} 必须是整数。") from exc

    if minimum is not None and result < minimum:
        raise ConfigError(f"{field_name} 不能小于 {minimum}。")
    return result


def parse_float(value: Any, field_name: str, default: float, minimum: float | None = None) -> float:
    """解析浮点数配置。"""
    if value in (None, ""):
        result = default
    else:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{field_name} 必须是数字。") from exc

    if minimum is not None and result < minimum:
        raise ConfigError(f"{field_name} 不能小于 {minimum}。")
    return result


def parse_bool(value: Any, field_name: str, default: bool = False) -> bool:
    """解析布尔配置。"""
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    raise ConfigError(f"{field_name} 必须是布尔值，可用值如 True / False。")


def parse_push_hour(value: Any) -> int | None:
    """解析整点推送配置。"""
    if value in (None, ""):
        return None
    try:
        hour = int(str(value).strip())
    except (TypeError, ValueError):
        return None

    if 0 <= hour <= 23:
        return hour
    raise ConfigError("PUSH_PLUS_HOUR 必须是 0 到 23 之间的整数。")


def parse_accounts(users_raw: Any, passwords_raw: Any) -> list[AccountCredential]:
    """解析账号列表。"""
    if not isinstance(users_raw, str) or not users_raw.strip():
        raise ConfigError("USER 未配置，无法执行。")
    if not isinstance(passwords_raw, str) or not passwords_raw.strip():
        raise ConfigError("PWD 未配置，无法执行。")

    users = [item.strip() for item in users_raw.split("#")]
    passwords = [item.strip() for item in passwords_raw.split("#")]

    if any(not item for item in users):
        raise ConfigError("USER 中存在空账号，请检查 # 分隔格式。")
    if any(not item for item in passwords):
        raise ConfigError("PWD 中存在空密码，请检查 # 分隔格式。")
    if len(users) != len(passwords):
        raise ConfigError(f"账号数长度[{len(users)}]和密码数长度[{len(passwords)}]不匹配。")

    return [
        AccountCredential(user=normalize_user_name(user), password=password)
        for user, password in zip(users, passwords)
    ]


def parse_app_config(config_dict: dict[str, Any]) -> AppConfig:
    """将原始 JSON 配置转换为运行配置。"""
    min_step = parse_int(config_dict.get("MIN_STEP"), "MIN_STEP", 18000, minimum=0)
    max_step = parse_int(config_dict.get("MAX_STEP"), "MAX_STEP", 20000, minimum=0)
    if min_step > max_step:
        raise ConfigError("MIN_STEP 不能大于 MAX_STEP。")

    sleep_gap = parse_float(config_dict.get("SLEEP_GAP"), "SLEEP_GAP", 5.0, minimum=0.0)
    use_concurrent = parse_bool(config_dict.get("USE_CONCURRENT"), "USE_CONCURRENT", default=False)
    push_plus_max = parse_int(config_dict.get("PUSH_PLUS_MAX"), "PUSH_PLUS_MAX", 30, minimum=1)

    push_config = push_util.PushConfig(
        push_plus_token=str(config_dict.get("PUSH_PLUS_TOKEN") or "").strip() or None,
        push_plus_hour=parse_push_hour(config_dict.get("PUSH_PLUS_HOUR")),
        push_plus_max=push_plus_max,
        push_wechat_webhook_key=str(config_dict.get("PUSH_WECHAT_WEBHOOK_KEY") or "").strip() or None,
        telegram_bot_token=str(config_dict.get("TELEGRAM_BOT_TOKEN") or "").strip() or None,
        telegram_chat_id=str(config_dict.get("TELEGRAM_CHAT_ID") or "").strip() or None,
    )

    return AppConfig(
        accounts=parse_accounts(config_dict.get("USER"), config_dict.get("PWD")),
        min_step=min_step,
        max_step=max_step,
        sleep_gap=sleep_gap,
        use_concurrent=use_concurrent,
        push_config=push_config,
    )


def load_app_config(config_path: str = CONFIG_FILE) -> AppConfig:
    """加载并校验运行配置。"""
    return parse_app_config(load_config_dict(config_path))


def build_token_store_from_env() -> TokenStore:
    """根据环境变量初始化 token 缓存。"""
    aes_key_raw = os.environ.get("AES_KEY")
    if not aes_key_raw:
        return TokenStore()

    aes_key = aes_key_raw.encode("utf-8")
    if len(aes_key) != 16:
        print("AES_KEY 无效，长度必须正好为 16 个字节，将跳过本地 token 加密缓存。")
        return TokenStore()

    token_store = TokenStore(aes_key=aes_key)
    token_store.load()
    if token_store.load_error:
        print(token_store.load_error)
    return token_store


class MiMotionRunner:
    """单个账号的步数执行器。"""

    def __init__(self, credential: AccountCredential, token_store: TokenStore):
        self.user_id: str | None = None
        self.device_id = str(uuid.uuid4())
        self.credential = credential
        self.token_store = token_store
        self.log_str = ""
        self.is_phone = credential.user.startswith("+86")

    def _save_tokens(
        self,
        access_token: str,
        login_token: str,
        app_token: str,
        user_id: str,
    ) -> None:
        self.user_id = user_id
        self.token_store.set(
            self.credential.user,
            {
                "access_token": access_token,
                "login_token": login_token,
                "app_token": app_token,
                "user_id": user_id,
                "access_token_time": get_time_ms(),
                "login_token_time": get_time_ms(),
                "app_token_time": get_time_ms(),
                "device_id": self.device_id,
            },
        )

    def login(self) -> str | None:
        """登录并获取 app_token。"""
        user_token_info = self.token_store.get(self.credential.user)
        if user_token_info is not None:
            access_token = user_token_info.get("access_token")
            login_token = user_token_info.get("login_token")
            app_token = user_token_info.get("app_token")
            self.device_id = str(user_token_info.get("device_id") or self.device_id)
            self.user_id = user_token_info.get("user_id")

            ok, msg = zepp_helper.check_app_token(app_token, self.user_id)
            if ok:
                self.log_str += "使用本地缓存的 app_token\n"
                return app_token

            self.log_str += f"app_token 失效，准备刷新：{msg}，上次更新时间：{user_token_info.get('app_token_time')}\n"
            refreshed_app_token, refresh_msg = zepp_helper.grant_app_token(login_token)
            if refreshed_app_token is not None:
                user_token_info["app_token"] = refreshed_app_token
                user_token_info["app_token_time"] = get_time_ms()
                self.token_store.set(self.credential.user, user_token_info)
                self.log_str += "刷新 app_token 成功\n"
                return refreshed_app_token

            self.log_str += (
                f"login_token 失效或刷新失败：{refresh_msg}，"
                f"上次更新时间：{user_token_info.get('login_token_time')}\n"
            )
            login_token, app_token, user_id, grant_msg = zepp_helper.grant_login_tokens(
                access_token,
                self.device_id,
                self.is_phone,
            )
            if login_token is not None and app_token is not None and user_id is not None:
                self._save_tokens(access_token, login_token, app_token, user_id)
                return app_token

            self.log_str += (
                f"access_token 已失效或登录失败：{grant_msg}，"
                f"上次更新时间：{user_token_info.get('access_token_time')}\n"
            )

        access_token, login_msg = zepp_helper.login_access_token(
            self.credential.user,
            self.credential.password,
        )
        if access_token is None:
            self.log_str += f"登录获取 access_token 失败：{login_msg}"
            return None

        login_token, app_token, user_id, grant_msg = zepp_helper.grant_login_tokens(
            access_token,
            self.device_id,
            self.is_phone,
        )
        if login_token is None or app_token is None or user_id is None:
            self.log_str += f"登录提取 access_token 后换取 app_token 失败：{grant_msg}"
            return None

        self._save_tokens(access_token, login_token, app_token, user_id)
        return app_token

    def login_and_post_step(self, min_step: int, max_step: int) -> tuple[str, bool]:
        """登录并发送步数。"""
        app_token = self.login()
        if app_token is None:
            return "登录失败", False

        step = random.randint(min_step, max_step)
        self.log_str += f"已设置固定随机步数范围({min_step}~{max_step})，本次随机值：{step}\n"
        ok, msg = zepp_helper.post_fake_brand_data(str(step), app_token, self.user_id)
        return f"修改步数（{step}）[{msg}]", ok


def run_single_account(
    total: int,
    index: int,
    credential: AccountCredential,
    app_config: AppConfig,
    token_store: TokenStore,
) -> dict[str, Any]:
    """执行单个账号。"""
    index_info = f"[{index + 1}/{total}]"
    log_str = f"[{format_now()}]\n{index_info}账号：{desensitize_user_name(credential.user)}\n"

    try:
        runner = MiMotionRunner(credential, token_store)
        exec_msg, success = runner.login_and_post_step(app_config.min_step, app_config.max_step)
        log_str += runner.log_str
        log_str += f"{exec_msg}\n"
        exec_result = {"user": credential.user, "success": success, "msg": exec_msg}
    except Exception:
        error_msg = f"执行异常：{traceback.format_exc()}"
        log_str += f"{error_msg}\n"
        exec_result = {"user": credential.user, "success": False, "msg": error_msg}

    print(log_str)
    token_store.persist()
    return exec_result


def execute(app_config: AppConfig, token_store: TokenStore) -> list[dict[str, Any]]:
    """执行全部账号。"""
    total = len(app_config.accounts)
    if app_config.use_concurrent:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(total, 10)) as executor:
            return list(
                executor.map(
                    lambda item: run_single_account(total, item[0], item[1], app_config, token_store),
                    enumerate(app_config.accounts),
                )
            )

    results = []
    for index, credential in enumerate(app_config.accounts):
        results.append(run_single_account(total, index, credential, app_config, token_store))
        if index < total - 1:
            time.sleep(app_config.sleep_gap)
    return results


def main() -> int:
    """程序入口。"""
    try:
        app_config = load_app_config()
    except ConfigError as exc:
        print(exc)
        return 1

    token_store = build_token_store_from_env()
    if not app_config.use_concurrent:
        print(f"多账号执行间隔：{app_config.sleep_gap} 秒")

    exec_results = execute(app_config, token_store)
    if token_store.enabled:
        token_store.persist()

    success_count = sum(1 for result in exec_results if result["success"])
    total = len(exec_results)
    summary = f"\n执行账号总数 {total}，成功：{success_count}，失败：{total - success_count}"
    print(summary)
    push_util.push_results(exec_results, summary, app_config.push_config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
