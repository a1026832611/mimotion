# mimotion

## 小米运动自动刷步数（支持邮箱登录）

基于 [TonyJiangWJ/mimotion](https://github.com/TonyJiangWJ/mimotion) 修改，面向本地运行。

- 小米运动 APP 现已改名 Zepp Life，下载注册时请搜索 Zepp Life。
- 注册账号后建议先去以下网站测试刷步数是否正常（不保证安全和有效性）：
    - https://steps.hubp.de/ 提示密码错误时可以多试几次或切换网络
    - https://bs.yanwan.store/run4/ 验证码 001 或 998
- 如无法刷步数同步到支付宝等，建议重新注册一个新的。

## 项目说明

本仓库是面向本地运行整理过的 `mimotion` 版本，默认使用本地 `config.json` 配置文件，通过 `python3 main.py` 执行。不再维护 GitHub Actions 工作流。

### 与上游的主要差异

- 仅支持本地运行，已移除 GitHub Actions 工作流文件。
- 步数逻辑为固定随机区间（`MIN_STEP ~ MAX_STEP`），不再按时间线性增长。
- 支持通过环境变量 `AES_KEY` 启用本地 token AES 加密缓存。
- 每个账号执行完成后立即持久化 token 缓存，避免中途异常丢失。
- 并发模式下线程数上限为 10。

## 项目结构

```
mimontion/
├── main.py                  # 主入口：配置解析、登录、刷步数
├── config.example.json      # 配置文件模板
├── requirements.txt         # Python 依赖
├── util/
│   ├── zepp_helper.py       # Zepp/华米 API 调用
│   ├── push_util.py         # 推送通知（PushPlus / 企业微信 / Telegram）
│   ├── aes_help.py          # AES-128-CBC 加解密
│   └── time_util.py         # 时间工具（北京时间）
├── tests/                   # 单元测试
│   ├── test_main.py
│   ├── test_push_util.py
│   └── test_zepp_helper.py
└── local/
    └── decrypt_data.py      # 调试用：解密 AES 加密内容
```

## 环境要求

- Python 3.10+
- 依赖库：`requests`、`pytz`、`pycryptodome`
- 可访问华米 / Zepp 相关接口的网络环境

## 快速开始

1. 安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

2. 复制示例配置并编辑：

```bash
cp config.example.json config.json
```

3. 编辑 `config.json`，填入你自己的账号、密码和步数范围。

4. 运行脚本：

```bash
python3 main.py
```

5. （可选）启用本地 token 加密缓存，设置 16 字节长度的 `AES_KEY`：

```bash
export AES_KEY="1234567890abcdef"
python3 main.py
```

## 配置文件说明

配置文件名固定为 `config.json`，内容示例如下：

```json
{
  "USER": "13800138000#demo@example.com",
  "PWD": "password1#password2",
  "MIN_STEP": "18000",
  "MAX_STEP": "20000",
  "PUSH_PLUS_TOKEN": "",
  "PUSH_PLUS_HOUR": "",
  "PUSH_PLUS_MAX": "30",
  "PUSH_WECHAT_WEBHOOK_KEY": "",
  "TELEGRAM_BOT_TOKEN": "",
  "TELEGRAM_CHAT_ID": "",
  "SLEEP_GAP": "5",
  "USE_CONCURRENT": "False"
}
```

| 字段名 | 说明 |
| --- | --- |
| `USER` | 小米运动 / Zepp Life 登录账号，支持手机号或邮箱。多账号用 `#` 分隔。 |
| `PWD` | 对应账号密码，多账号时数量必须与 `USER` 一致，也用 `#` 分隔。 |
| `MIN_STEP` | 随机步数下限。 |
| `MAX_STEP` | 随机步数上限。每次执行会在此区间内固定随机。 |
| `PUSH_PLUS_TOKEN` | PushPlus 推送 token，可留空。 |
| `PUSH_PLUS_HOUR` | 只在北京时间某个整点推送消息（0-23），留空则每次都推送。 |
| `PUSH_PLUS_MAX` | 单次推送最多展示多少个账号详情，超过后仅显示摘要。 |
| `PUSH_WECHAT_WEBHOOK_KEY` | 企业微信机器人 webhook key，可留空。 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot token，可留空。 |
| `TELEGRAM_CHAT_ID` | Telegram chat id，需要和 `TELEGRAM_BOT_TOKEN` 一起配置。 |
| `SLEEP_GAP` | 串行模式下多账号之间的间隔秒数，不能小于 0。 |
| `USE_CONCURRENT` | 是否启用并发执行（`True` / `False`），启用后 `SLEEP_GAP` 不生效，最大并发数为 10。 |

## 本地 token 缓存

- 默认不保存登录 token。设置环境变量 `AES_KEY`（必须正好 16 字节）后启用。
- token 加密保存到 `encrypted_tokens.data`，每个账号执行后立即更新。
- 密钥错误时程序会忽略旧缓存并重新登录，不会崩溃。
- `encrypted_tokens.data` 已在 `.gitignore` 中，不建议提交。

## 推送说明

支持三种推送渠道，按需配置：

| 渠道 | 配置字段 |
| --- | --- |
| PushPlus | `PUSH_PLUS_TOKEN` |
| 企业微信机器人 | `PUSH_WECHAT_WEBHOOK_KEY` |
| Telegram Bot | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` |

- `PUSH_PLUS_HOUR` 按本地运行时的北京时间整点判断是否推送。
- 账号数超过 `PUSH_PLUS_MAX` 时，推送仅保留摘要。
- 未配置字段时自动跳过对应渠道。

## 运行测试

```bash
python3 -m pytest tests/
```

## 常见问题

**账号数量和密码数量不匹配？**
`USER` 和 `PWD` 使用 `#` 分隔后的数量不同，或其中某一项为空。

**支付宝 / 微信步数没有同步？**
- 确认使用的是小米运动 / Zepp Life 账号，而不是小米账号。
- 先去上述网站验证账号是否可正常刷步。
- 通常需要在小米运动里重新登录并重新绑定第三方平台。

**提示 token 缓存损坏？**
`AES_KEY` 变了或缓存文件与密钥不匹配。重新运行一次即可。

**同一网络下多个账号容易失败？**
上游接口有风控限制，同 IP 高频登录多账号可能触发限流，请控制频率或分散网络。

## 注意事项

1. 账号必须是小米运动 / Zepp Life 账号，不是小米账号。
2. 多账号场景下确认账号和密码一一对应。
3. 小米运动本身不直接显示刷步成功，关联平台同步后才有变化。
4. 接口行为和风控规则可能随官方调整而变化。

## 致谢与免责声明

- 基于上游仓库 [TonyJiangWJ/mimotion](https://github.com/TonyJiangWJ/mimotion) 调整。
- 登录加密参考 [hanximeng/Zepp_API](https://github.com/hanximeng/Zepp_API/blob/main/index.php)。
- 本仓库仅用于学习和研究，请自行评估账号安全、接口变更和使用风险。
