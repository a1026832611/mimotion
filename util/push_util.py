import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

from util.time_util import format_now, get_beijing_time


REQUEST_TIMEOUT = 10


@dataclass(frozen=True)
class PushConfig:
    """推送配置。"""

    push_plus_token: str | None = None
    push_plus_hour: int | None = None
    push_plus_max: int = 30
    push_wechat_webhook_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


def build_wechat_content(title: str, content: str) -> str:
    return f"# {title}\n{content}"


def push_plus(token: str, title: str, content: str) -> None:
    """PushPlus 推送。"""
    request_url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html",
        "channel": "wechat",
    }
    try:
        response = requests.post(request_url, data=data, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            print(f"pushplus 推送失败，status: {response.status_code}")
            return
        json_res = response.json()
        print(f"pushplus 推送完毕：{json_res.get('code')}-{json_res.get('msg')}")
    except requests.exceptions.RequestException as exc:
        print(f"pushplus 推送网络异常：{exc}")
    except ValueError:
        print("pushplus 推送失败，响应不是合法 JSON。")


def push_wechat_webhook(key: str, title: str, content: str) -> None:
    """企业微信 WebHook 推送。"""
    request_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
    payload = {
        "msgtype": "markdown_v2",
        "markdown_v2": {
            "content": build_wechat_content(title, content),
        },
    }
    try:
        response = requests.post(request_url, json=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            print(f"企业微信推送失败，status: {response.status_code}")
            return
        json_res = response.json()
        if json_res.get("errcode") == 0:
            print(f"企业微信推送完毕：{json_res.get('errmsg')}")
        else:
            print(f"企业微信推送失败：{json_res.get('errmsg', '未知错误')}")
    except requests.exceptions.RequestException as exc:
        print(f"企业微信推送异常：{exc}")
    except ValueError:
        print("企业微信推送失败，响应不是合法 JSON。")


def push_telegram_bot(bot_token: str, chat_id: str, content: str) -> None:
    """Telegram Bot 推送。"""
    request_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": int(chat_id),
        "text": content,
        "parse_mode": "HTML",
    }
    try:
        response = requests.post(request_url, json=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            print(f"telegram bot 推送失败，status: {response.status_code}")
            return
        json_res = response.json()
        if json_res.get("ok") is True:
            message_id = json_res.get("result", {}).get("message_id")
            print(f"telegram bot 推送完毕：{message_id}")
        else:
            print(f"telegram bot 推送失败：{json.dumps(json_res, ensure_ascii=False)}")
    except requests.exceptions.RequestException as exc:
        print(f"telegram bot 推送异常：{exc}")
    except ValueError:
        print("telegram bot 推送失败，响应不是合法 JSON。")


def not_in_push_time_range(config: PushConfig, now: datetime | None = None) -> bool:
    """判断当前是否不在推送时间范围。"""
    if config.push_plus_hour is None:
        return False

    current_hour = get_beijing_time(now).hour
    if current_hour == config.push_plus_hour:
        print(f"当前设置推送整点为：{config.push_plus_hour}，当前整点为：{current_hour}，执行推送。")
        return False

    print(f"当前北京时间整点为：{current_hour}，不在配置的推送时间 {config.push_plus_hour}，跳过推送。")
    return True


def push_results(exec_results: list[dict[str, Any]], summary: str, config: PushConfig) -> None:
    """执行全部推送。"""
    if not_in_push_time_range(config):
        return
    push_to_push_plus(exec_results, summary, config)
    push_to_wechat_webhook(exec_results, summary, config)
    push_to_telegram_bot(exec_results, summary, config)


def push_to_push_plus(exec_results: list[dict[str, Any]], summary: str, config: PushConfig) -> None:
    """推送到 PushPlus。"""
    if not config.push_plus_token or config.push_plus_token == "NO":
        print("未配置 PUSH_PLUS_TOKEN，跳过 pushplus 推送。")
        return

    html = f"<div>{summary}</div>"
    if len(exec_results) > config.push_plus_max:
        html += "<div>账号数量过多，请查看本地日志输出获取完整结果。</div>"
    else:
        html += "<ul>"
        for exec_result in exec_results:
            if exec_result["success"]:
                html += (
                    f'<li><span>账号：{exec_result["user"]}</span>'
                    f'刷步数成功，接口返回：{exec_result["msg"]}</li>'
                )
            else:
                html += (
                    f'<li><span>账号：{exec_result["user"]}</span>'
                    f'刷步数失败，失败原因：{exec_result["msg"]}</li>'
                )
        html += "</ul>"

    push_plus(config.push_plus_token, f"{format_now()} 刷步数通知", html)


def push_to_wechat_webhook(exec_results: list[dict[str, Any]], summary: str, config: PushConfig) -> None:
    """推送到企业微信。"""
    if not config.push_wechat_webhook_key or config.push_wechat_webhook_key == "NO":
        print("未配置 PUSH_WECHAT_WEBHOOK_KEY，跳过企业微信推送。")
        return

    content = f"## {summary}"
    if len(exec_results) > config.push_plus_max:
        content += "\n- 账号数量过多，请查看本地日志输出获取完整结果。"
    else:
        for exec_result in exec_results:
            if exec_result["success"]:
                content += f'\n- 账号：{exec_result["user"]} 刷步数成功，接口返回：{exec_result["msg"]}'
            else:
                content += f'\n- 账号：{exec_result["user"]} 刷步数失败，失败原因：{exec_result["msg"]}'

    push_wechat_webhook(config.push_wechat_webhook_key, f"{format_now()} 刷步数通知", content)


def push_to_telegram_bot(exec_results: list[dict[str, Any]], summary: str, config: PushConfig) -> None:
    """推送到 Telegram。"""
    if not config.telegram_bot_token or config.telegram_bot_token == "NO":
        print("未配置 TELEGRAM_BOT_TOKEN，跳过 telegram 推送。")
        return
    if not config.telegram_chat_id:
        print("未配置 TELEGRAM_CHAT_ID，跳过 telegram 推送。")
        return

    html = f"<b>{summary}</b>"
    if len(exec_results) > config.push_plus_max:
        html += "<blockquote>账号数量过多，请查看本地日志输出获取完整结果。</blockquote>"
    else:
        for exec_result in exec_results:
            if exec_result["success"]:
                html += (
                    f'<pre><blockquote>账号：{exec_result["user"]}</blockquote>'
                    f'刷步数成功，接口返回：<b>{exec_result["msg"]}</b></pre>'
                )
            else:
                html += (
                    f'<pre><blockquote>账号：{exec_result["user"]}</blockquote>'
                    f'刷步数失败，失败原因：<b>{exec_result["msg"]}</b></pre>'
                )

    push_telegram_bot(config.telegram_bot_token, config.telegram_chat_id, html)
