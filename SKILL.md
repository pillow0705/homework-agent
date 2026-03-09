---
name: homework-agent
description: 接收作业文件（txt/md/pdf/docx），调用 Claude 生成模拟人类作答的 LaTeX 解答，编译成 PDF 返回给客户端。服务运行在 5500 端口。
---

# Homework Agent Skill

接收作业文件，用 Claude 生成完整、自然的作业答案，输出为 PDF（或 LaTeX 源码）。

## 文件结构

```
homework-agent/
├── SKILL.md          # 本文档
├── server.py         # Flask 服务端（端口 5500）
├── client.py         # CLI 客户端（在本地机器上运行）
├── requirements.txt  # Python 依赖
└── start.sh          # 服务启动脚本
```

## 服务端部署

### 1. 安装依赖

```bash
pip3 install -r requirements.txt
```

### 2. 设置 API Key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 3. 启动服务

```bash
# 默认端口 5500
./start.sh

# 指定端口
./start.sh 5800
```

服务启动后监听 `0.0.0.0:5500`，对外暴露两个接口：

| 方法 | 路由 | 说明 |
|------|------|------|
| GET  | `/health` | 健康检查 |
| POST | `/homework` | 提交作业文件，返回 PDF/TeX |

`/homework` 接口参数：
- `files`（multipart，可多个）：作业文件
- `format`（form field，可选）：`pdf`（默认）或 `tex`

## 客户端使用

在**本地机器**上运行 `client.py`：

```bash
# 进入含作业文件的目录
cd ~/my-homework/

# 连接服务器（替换为实际 IP）
python3 /path/to/client.py --server http://SERVER_IP:5500

# 返回 TeX 源码而非 PDF
python3 client.py --server http://SERVER_IP:5500 --format tex

# 指定输出文件名
python3 client.py --server http://SERVER_IP:5500 --out hw1_answer.pdf

# 通过环境变量设置默认服务器
export HOMEWORK_SERVER=http://SERVER_IP:5500
python3 client.py
```

运行后会显示当前目录中所有支持的文件，输入编号选择要上传的文件：

```
Found the following files:

  [ 1] hw1.pdf  (128.3 KB)
  [ 2] notes.md  (4.2 KB)
  [ 3] problem_set.docx  (88.7 KB)

Enter file numbers to upload (e.g. 1 3 4), or 'all', or 'q' to quit:
> 1 3

Uploading 2 file(s) to http://SERVER_IP:5500/homework ...

Done! Answer saved to: /home/user/my-homework/answer.pdf
```

## 支持的文件类型

| 扩展名 | 解析方式 |
|--------|----------|
| `.txt` | 直接读取 |
| `.md` / `.markdown` | 直接读取 |
| `.pdf` | pdfplumber 提取文本 |
| `.docx` / `.doc` | python-docx 提取段落 |

## 防火墙配置（腾讯云/阿里云）

需要在安全组中开放 TCP 5500 端口（入站）。

```bash
# 或使用 iptables 临时开放
iptables -I INPUT -p tcp --dport 5500 -j ACCEPT
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ANTHROPIC_API_KEY` | 必填 | Anthropic API Key |
| `HOMEWORK_PORT` | `5500` | 服务端监听端口 |
| `HOMEWORK_SERVER` | `http://127.0.0.1:5500` | 客户端默认服务器地址 |

## 工作原理

```
客户端                          服务端
  │                               │
  │── 扫描本地目录 ──────────────>│
  │<─ 用户选择文件 ───────────────│
  │── POST /homework (multipart) >│
  │                               │── 提取文件文本
  │                               │── 调用 Claude (claude-sonnet-4-6)
  │                               │── 生成 LaTeX 源码
  │                               │── pdflatex 编译 (×2)
  │<─ 返回 answer.pdf ────────────│
  │── 保存到本地 ─────────────────│
```

## 依赖

- Python 3.10+
- `pdflatex`（TeX Live，服务端已安装）
- `anthropic`, `flask`, `pdfplumber`, `python-docx`, `requests`
