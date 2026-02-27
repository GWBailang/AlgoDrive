最近用 cf 遂穿把旧电脑整成服务器了，于是写了个简单的网盘。当然网盘只是为了自己用。

免责声明：`README.md` 99% 的内容由 AI 编写。

# AlgoDrive

**AlgoDrive** 是一个为开发者（特别是算法竞赛选手）设计的轻量级、高性能、单文件架构的“家里云”文件存储系统。它通过分段上传技术打破了 Cloudflare Tunnel 免费版 100MB 的上传枷锁。

> [!CAUTION]
> **WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.**

---

## 核心特性 (Features)

* **$O(1)$ 内存分段上传**: 采用前端 `Blob.slice()` 切片与后端 `shutil.copyfileobj` 流式合并，无论上传 10GB 还是 100GB，服务器内存占用始终保持平稳。
* **物理隔离架构**: `files/`（存储区）与 `temp/`（临时区）在物理路径上彻底隔离，从根源上杜绝了临时碎片在前端暴露的风险。
* **硬核路径保护**: 内置递归 `is_safe_path` 校验，配合 `os.path.abspath` 指纹比对，无惧任何 `../` 路径穿透攻击。
* **算法选手友好 (CP-Style)**:
* **Single-File Monolith**: 核心后端逻辑全部集中在 `app.py`，逻辑链条一览无余。
* **Config-Driven**: 所有的常量（如分段大小、清理时限、登录冷却）均由 `config.json` 统一管理。


* **Cloudflare 深度集成**: 内置 WSGI 中件间，自动拦截并解析 `CF-Connecting-IP`，让系统日志真实记录每一条访问者的真实 IP。

---

## 技术规格

* **后端**: Python 3.12+ / Flask
* **前端**: 原生 JavaScript (Async/Await) + HTML5 `dataset` 通讯
* **安全**: PBKDF2/Scrypt 密码哈希 + 针对 IP 的频率限制 (Cooldown)

---

## 快速开始

### 1. 环境初始化

新版本 Ubuntu 需要安装 venv 虚拟环境。

```bash
git clone https://github.com/你的用户名/AlgoDrive.git
cd AlgoDrive
python3 -m venv .venv
source .venv/bin/activate
pip install flask

```

### 2. 配置 `config.json`

将 `config.json.example` 重命名为 `config.json` 并填写你的配置：

```json
{
    "MAX_CONTENT_LENTH_MB": 1024,
    "CHUNK_SIZE_MB": 10,
    "TEMP_CLEANUP_HOURS": 24,
    "SECRET_KEY": "replace-this-with-a-very-long-random-string",
    "STORAGE_DIR": "files",
    "LOGIN_CD_S": 3,
    "USER": {
        "username": "admin",
        "password_hash": "paste_your_generated_hash_here"
    }
}

```

### 3. 运行

```bash
python3 app.py

```

---

## 项目结构

```text
AlgoDrive/
├── app.py              # 核心单体应用 (Back-end)
├── config.json         # 配置文件 (Local only)
├── gen_hash.py         # 密码哈希生成工具
├── files/              # 网盘文件存放区 (Auto-created)
├── temp/               # 分段上传缓存区 (Auto-created)
├── templates/          # Jinja2 模板
└── static/             # CSS/Static 资源

```

---

## 安全防御说明

本项目通过三层校验保护你的数据：

1. **身份校验**: 基于 Session 的状态管理。
2. **频率校验**: `last_login_times` 字典记录 IP 失败尝试，强制 2s+ 的算法级冷却。
3. **路径校验**: 所有的文件操作（Read/Write/Delete）均会执行 `is_safe_path` 检查，确保操作范围严格限定在 `STORAGE_DIR` 或 `TEMP_DIR` 内。

---

## 协议

**MIT License**