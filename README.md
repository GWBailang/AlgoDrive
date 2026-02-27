最近用 cf 遂穿把旧电脑整成服务器了，于是写了个简单的网盘。当然网盘只是为了自己用。

免责声明：`README.md` 99% 的内容由 AI 编写。

# AlgoDrive

**AlgoDrive** 是一个为个人打造的、轻量级且高度安全的“家里云”文件管理系统。它抛弃了过度封装的复杂架构，采用算法竞赛风格的开发范式，追求极致的逻辑清晰度与单文件可移植性。

> [!CAUTION]
> **WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.**

---

## 项目亮点 (Why AlgoDrive?)

* **CP-Style Monolith Architecture**: 核心逻辑 100% 集中于单个 Python 文件。没有冗余的目录跳转，代码逻辑一览无余，符合算法竞赛选手的阅读与调试习惯，实现 $O(1)$ 级别的维护成本。
* **Cloudflare Optimized**: 原生支持 Cloudflare Tunnel 穿透，自动解析 `CF-Connecting-IP` 头部，精准记录访客真实 IP。
* **Security-First Design**:
* 采用 `PBKDF2/Scrypt` 强哈希算法存储凭证，拒绝明文存储。
* 内置 **IP 登录冷却机制**，有效抵御暴力破解攻击。
* 严密的 **Path Sanitization** 逻辑，彻底封死 `../` 路径穿透漏洞。


* **UI 100% 自定义**: 逻辑与表现层通过 Jinja2 模板解耦，支持通过外部 `style.css` 快速换肤。

---

## 技术规格

* **Backend**: Python 3.12+ / Flask
* **Security**: Werkzeug Security Utils (Hash & Check)
* **Template**: Jinja2 Template Engine
* **Config**: Standard JSON Configuration

---

## 快速部署

### 1. 克隆与环境初始化

在某些新版本 Ubuntu 中，需要使用 `venv` 虚拟环境。

```bash
git clone https://github.com/your_name/AlgoDrive.git
cd AlgoDrive
python3 -m venv .venv
source .venv/bin/activate
pip install flask

```

### 2. 配置 `config.json`

请根据 `config.json.example` 创建你的配置文件：

```json
{
    "MAX_CONTENT_LENGTH_MB": 1024,
    "SECRET_KEY": "RANDOM_STRING_HERE",
    "STORAGE_DIR": "files",
    "LOGIN_CD_S": 2,
    "USER": {
        "username": "admin",
        "password_hash": "YOUR_HASHED_PASSWORD"
    }
}

```

### 3. 运行

```bash
python3 app.py

```

---

## 安全提示

本项目默认运行在 Flask 内置的开发服务器上。若需在公网环境长期稳定运行，建议使用 `gunicorn` 或 `uWSGI` 进行包装：

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 app:app

```

---

## 开源协议

**MIT License** - 保持极简，拥抱自由。