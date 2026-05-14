# youtube-kol-eva

> 给一个 YouTube 频道 + 报价，自动算出 KOL 评估指标，**直接给你"合作 / 砍价 / 试水 / 不合作"的建议**。

**👋 给非技术背景的你：** 这个 README 是按"零基础也能跑通"的标准写的。每一步都告诉你**要打什么命令**和**这一步在干嘛**。卡住直接跳到 [出问题怎么办](#出问题怎么办)。

---

## 这个工具能干嘛

你给它两样东西：
- 一个 YouTube 频道（比如 `@MrBeast`、`https://www.youtube.com/@MrBeast`、或频道 ID）
- 这个频道一条赞助视频的报价（比如 5000 美元）

它会：
1. 拉这个频道**最近 10 条视频**的 views / likes / comments
2. 拉这 10 条视频下**每条最多 100 条**顶级评论的发布者 ID
3. 算 6 个核心指标 + 2 个评论真实性指标
4. 跑评分 + 给 verdict：**推进合作 / 砍价合作 / 小单试水 / 暂缓 / 不合作**
5. 砍价合作时直接告诉你目标价 + 一句可以发给 KOL 的压价说辞

整个过程 30–60 秒。用的是 YouTube 官方 Data API v3，**免费**（每天 10000 配额，跑 100+ 个频道都用不完）。

---

## 它会算哪些指标

### 6 个核心指标

| 指标 | 公式 | 怎么读 |
|------|------|--------|
| **ER（粉丝互动率）** | (likes+comments) / subscribers | 1% 算正常，2% 以上算优秀 |
| **View ER（曝光互动率）** | (likes+comments) / avg_views | 排除僵尸粉之后的真实互动 |
| **C/L Ratio（评论深度比）** | comments / likes | < 1% 是买赞警报 |
| **Reach Rate（粉丝触达率）** | avg_views / subscribers | YouTube 算法在不在推 |
| **数据稳定性** | max_views / min_views | < 5x 健康，> 10x 数据可疑 |
| **CPM（千次曝光成本）** | price / (avg_views/1000) | 越低越划算 |

### 2 个评论真实性指标（这是 youtube-kol-eva 独有的）

| 指标 | 公式 | 怎么读 |
|------|------|--------|
| **Author uniqueness（评论人独立度）** | unique_authors / total_comments | 越高越真实；< 50% 重度水军 |
| **Cross-video repetition（跨视频重复率）** | 同一账号在 ≥ 2 个视频下评论的占比 | 越低越真实；> 40% 是水军刷遍所有视频的典型信号 |

### 综合评分（满分 100）

| 维度 | 满分 | 说明 |
|------|------|------|
| CPM 性价比 | 30 | 对比你设定的垂类基准（默认 tech/AI：≤ 80 USD acceptable） |
| ER 粉丝互动 | 20 | |
| View ER 互动质量 | 15 | |
| 评论真实性 | 25 | author_uniqueness + cross_video_repetition + C/L Ratio 综合 |
| 数据稳定性 | 10 | |

### 一票否决（红线）

任意一条触发就直接判 **不合作**：

- C/L Ratio < 1% 且 ER < 0.1% → 买赞模式
- Author uniqueness < 40% → 重度水军
- Cross-video repetition > 50% → 同一批账号刷遍所有视频
- 数据波动 > 10x → 不可信
- 样本 < 3 条视频

### 决策树

| 分数区间 | 条件 | 结论 |
|----------|------|------|
| ≥ 75 | 无红线 | **推进合作** |
| 60–74 | CPM ≤ 可接受 | **推进合作** |
| 60–74 | CPM 在可接受–expensive 之间 | **砍价合作**（给目标价 + 压价说辞）|
| 45–59 | | **小单试水** |
| 30–44 | | **暂缓**（数据不够或波动大，等等再看）|
| < 30 或触发红线 | | **不合作** |

垂类的 CPM 区间默认是科技/AI，可以在 `.env` 里改 `DEFAULT_VERTICAL`。

---

## 你需要先准备什么？

1. **一台电脑**：Mac / Windows / Linux 都行
2. **一个 Google 账号**：用于开 YouTube Data API（**免费**）
3. **一点终端时间**：第一次大约 10 分钟把环境装好

> "终端"指 Mac 的 **Terminal**（应用程序 → 实用工具 → 终端）或 Windows 的 **PowerShell**。本文出现的命令贴进去回车就行。

---

## 第一次安装（约 10 分钟）

### 第 1 步：装 uv

uv 是 Python 的包管理器。

**Mac / Linux：**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows（PowerShell）：**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

装完之后**关掉终端再开一个新的**，确认：
```bash
uv --version
```

### 第 2 步：把代码下载到本地

挑个文件夹（比如 `~`），cd 进去，然后：
```bash
git clone https://github.com/shuangw209/youtube-kol-eva.git
cd youtube-kol-eva
```

### 第 3 步：装依赖

```bash
uv sync
```

### 第 4 步：开 YouTube API key

YouTube Data API v3 是 Google 的官方 API，免费配额每天 10000 unit（评估 100+ 个频道用不完）。

**步骤：**

1. 打开 https://console.cloud.google.com/
（Google 账号登录，第一次同意条款）

2. 顶部左边项目下拉框 → **NEW PROJECT** → 名字随便（比如 `youtube-kol-eva`）→ 创建完自动切到这个项目

3. 顶部搜索框搜 **YouTube Data API v3** → 点结果 → 蓝色 **ENABLE** 按钮

4. 左边菜单 → **APIs & Services → Credentials**
顶部 **+ CREATE CREDENTIALS** → 选 **API key**

5. 弹窗显示一串新生成的 key，复制下来

6. **强烈建议**：在 Credentials 列表点这个 key 进编辑页 → **API restrictions** → Restrict key → 勾 **YouTube Data API v3** → Save。这样这个 key 只能调 YouTube API，泄漏了也调不了别的。

### 第 5 步：填 `.env`

```bash
cp .env.example .env
```

打开 `.env`：

**Mac**：
```bash
open -e .env
```

**Windows**（PowerShell）：
```powershell
notepad .env
```

**Linux**：
```bash
nano .env
```

把上一步生成的 API key 填到 `YOUTUBE_API_KEY=` 后面，保存。其它字段保持默认就行。

### 第 6 步：自检

```bash
uv run ytkol doctor
```

看到 `✓ YouTube API key works.` 就 OK 了。

✅ **环境就绪。**

---

## 日常使用

> ⚠️ **每次新开终端都先 cd 进项目目录**，否则 `uv run` 找不到环境，会报 `Failed to spawn: ytkol`。
>
> ```bash
> cd ~/youtube-kol-eva
> ```

### 最简单的用法

```bash
uv run ytkol evaluate @MrBeast --price 5000
```

等 30–60 秒，会看到：

- **KOL Snapshot**：频道名、订阅数、报价、采样数、平均 views/likes/comments、评论收集统计
- **The 6 Core Metrics**：6 个核心指标 + 公式
- **Comment Authenticity**：2 个评论真实性指标
- **Verdict**：决策（推进 / 砍价 / 试水 / 暂缓 / 不合作）+ 评分明细 + 红线 +（砍价时）目标价 + 谈判说辞 + 说明
- **Samples**：用到的 10 个视频明细，方便你核对

### 常用参数

```bash
# 多采样几条
uv run ytkol evaluate @MrBeast --price 5000 --recent-n 20

# 用人民币标价（注意：只是标签，不做汇率换算）
uv run ytkol evaluate @MrBeast --price 35000 --currency CNY

# 同时把完整 JSON 报告存到文件
uv run ytkol evaluate @MrBeast --price 5000 --json out.json

# 切换垂类（CPM 基准会变）
uv run ytkol evaluate @SomeGamer --price 1500 --vertical gaming

# 包含 Shorts（默认会跳过 ≤ 60 秒的视频）
uv run ytkol evaluate @MrBeast --price 5000 --include-shorts

# 直接用频道 URL / 视频 URL 当输入也行
uv run ytkol evaluate https://www.youtube.com/@MrBeast --price 5000
uv run ytkol evaluate https://www.youtube.com/watch?v=dQw4w9WgXcQ --price 800
```

完整参数表：
```bash
uv run ytkol evaluate --help
```

---

## 怎么读懂结果

### 红线信号（看到立刻警觉）

| 现象 | 可能的问题 |
|------|-----------|
| Author uniqueness < 50% | 评论区水军比例高 |
| Cross-video repetition > 40% | 同一批账号在所有视频下刷评论 |
| C/L Ratio < 1% | 评论太少 vs 点赞 → 买赞 |
| Stability > 10x | 数据不稳定，可能就一两条爆款 |
| Reach Rate < 1% | 算法不推这个号 |

### 推进合作之前再看一下

- **Verdict 给的"推进合作"不是 100% 安全**——它只是基于公开指标的量化判断。最终决策前，建议人工抽查 3–5 条最近视频的评论区是不是真在讨论内容
- **CPM 是横向比较工具**，单看一个号意义不大。建议把同类的 5–10 个 KOL 都跑一遍，按 CPM 排序

---

## 出问题怎么办

### "Failed to spawn: ytkol" / "No such file or directory"
你新开了终端没 cd 进项目目录。先：
```bash
cd ~/youtube-kol-eva
```

### "uv: command not found"
关掉终端再开一个新的，让系统重新 load PATH。

### `ytkol doctor` 报 "API key rejected by YouTube"
- 检查 `.env` 里 `YOUTUBE_API_KEY` 是不是粘贴对了（没多余空格、没引号）
- 检查项目里**是否启用了 YouTube Data API v3**（Cloud Console → APIs & Services → Library → YouTube Data API v3 → Enable）
- 如果你设了 API restriction，确认 YouTube Data API v3 在允许列表里

### `evaluate` 报 "YouTube API quota exceeded"
免费配额每天重置（太平洋时间凌晨）。一个评估大约用 13 unit，每天能跑 700+ 次。如果突然耗完，多半是一直失败重试导致的。等到第二天再试。

### Channel not found
- 确认 handle 拼对没（区分大小写）
- 试着改用频道 ID（`UC...`）或完整 URL

### 评分总是偏低
- 检查 `--vertical` 是不是对——默认 `tech_ai` 的 CPM 阈值偏宽松；游戏 KOL 用 `gaming` 阈值更严
- 在 `ytkol/config.py` 里直接改 `VERTICALS` 的数字，不会触发任何复杂事

---

## 项目结构

```
youtube-kol-eva/
├── README.md                     ← 你正在看的这个
├── pyproject.toml                ← 项目定义（依赖等）
├── .env.example                  ← 配置模板
├── .gitignore
├── ytkol/
│   ├── cli.py                    ← evaluate / doctor 命令
│   ├── client.py                 ← YouTube Data API 封装
│   ├── url_utils.py              ← 解析 @handle / URL / 频道 ID / 视频 URL
│   ├── calculator.py             ← 6 个指标 + 评论真实性
│   ├── verdict.py                ← 评分 + 决策 + 谈判说辞
│   ├── config.py                 ← 垂类 CPM 区间 + 评分权重
│   ├── report.py                 ← 终端表格 + JSON 输出
│   └── models.py                 ← Sample / Metrics / Verdict / Report
└── tests/
    ├── test_calculator.py
    ├── test_verdict.py
    └── test_url_utils.py
```

跑测试：
```bash
uv run pytest
```

---

## 想自己调

### 改垂类 / CPM 阈值
打开 `ytkol/config.py`，找到 `VERTICALS` 字典：

```python
VERTICALS = {
    "tech_ai": CpmBands(excellent=25, good=50, acceptable=80, expensive=150),
    ...
}
```

直接改数字。`acceptable` 是你愿意接受的上限；超过 `expensive` 会被严重扣分。

### 改评分权重
同文件下面 `WEIGHTS` 字典，五个维度权重和必须等于 100。

### 改评分阈值（多少分对应什么决策）
打开 `ytkol/verdict.py`，函数 `score_and_verdict` 里那串 if/elif，直接改数字。

---

## 安全 & 配额

- **YouTube API key 像密码一样对待**：`.gitignore` 已经把 `.env` 排除掉了，不会进 git。
- 别在公开场合贴 key。如果不小心泄漏，去 Cloud Console 删掉重建。
- 单个评估约 13 quota unit，免费 10000/天 = 700+ 评估/天。如果你要批量跑很多频道，注意配额。

---

## 后续想加的

- [ ] 批量评估：一个 CSV 进，一个 CSV 出
- [ ] Notion / Sheets 输出
- [ ] 评论文本的 NLP 分析（情绪、垃圾内容比例）
- [ ] 与 [twitter-kol-eva](https://github.com/shuangw209/twitter-kol-eva) 联动，对同一 KOL 跨平台对比

需求随时开 issue 或在频道里说。

---

## License

MIT
