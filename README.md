<h1 align="center">🍔🛵 麦顺路 McRoutePin</h1>

<p align="center">
  <strong>麦乐送拼单墙 —— 附近一起点，骑手一趟送，配送费五折起</strong><br/>
  <em>麦当劳程序员创意开发大赛参赛作品 · 基于麦当劳 MCP</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-blue" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="MCP" src="https://img.shields.io/badge/MCP-McDonald's%20China-red" />
  <img alt="Deps" src="https://img.shields.io/badge/dependencies-zero-brightgreen" />
  <img alt="Tests" src="https://img.shields.io/badge/tests-20%20passed-brightgreen" />
</p>

<p align="center">
  <a href="https://mrezzz0822.github.io/mcd-pindan-skill/demo/index.html">▶ <strong>在线演示：拖动三个点，实时看撮合结果</strong></a>
  <br/>
  <sub>不用 clone、不用 Token、不用装环境</sub>
</p>

---

## 📖 目录

[项目介绍](#-项目介绍) · [效果演示](#-效果演示) · [核心算法](#-核心算法) · [安装方法](#-安装方法) · [使用示例](#-使用示例) · [在 Agent 中使用](#-在-agent-中使用) · [目标用户](#-目标用户) · [项目结构](#-项目结构) · [边界与声明](#-边界与声明)

---

## 📖 项目介绍

**一句话介绍：** 麦顺路（McRoutePin）是一个基于麦当劳 MCP 的麦乐送拼单墙 Skill——把"附近正在一起点单的人"亮出来，用顺路度算法撮合最合适的两个人拼成一趟配送。

一个人点麦乐送，9 元配送费占客单价的两成；其实同一门店、同一时间，你身边常常还有别人也在点。**麦顺路**把这层信息亮出来：像拼多多一样看到"附近正在一起点单的人"，挑最顺路的一位成团——骑手只跑一趟，配送费双方**各省 35%~50%**。

**一个设计，两端受益：**

- **给用户**：拼单墙 + 顺路度撮合。不用拉群、不用口算，转发一张拼单卡片即可成团，双方省得一样多（对称分摊，谁发起谁不吃亏）。
- **给麦当劳**：麦乐送是**自配送**，平台完全掌握同一门店的实时订单流。撮合引擎输出的「派单建议」（谁和谁合并、先送谁、绕路多少）可直接作为平台侧合单调度信号——骑手单趟多带一单，履约成本几乎不变，而合并配送费（¥9.0~¥11.7）高于单趟单订（¥9），**用户少付、平台多赚、骑手不多跑**，三方共赢。

> 与美团「拼好饭」拼餐费不同，麦顺路拼的是**配送费**——不改变商品价格体系，只分摊履约成本。

## ✨ 效果演示

### 在线可视化（推荐，双击即开，无需 Token）

打开 [`demo/index.html`](demo/index.html)：拖动地图上的门店、发起人、伙伴三个点，实时看到绕路比、三段距离、派单建议和双方各付多少。也可以试试「拼单墙」模式，看引擎如何从 3 个候选里挑出最顺路的那个人。

### 命令行 Demo（无需任何 Token）

```bash
git clone https://github.com/Mrezzz0822/mcd-pindan-skill.git
cd mcd-pindan-skill
python demo.py
```

核心输出（张三打开拼单墙，墙上有 3 位附近正在点单的用户）：

```
撮合引擎：按顺路程度为每位候选打分排序
  ✅ 赵六: 绕路比 1.00 → 深度顺路，一趟总里程 0.90 km
  ✅ 李四: 绕路比 1.01 → 深度顺路，一趟总里程 1.01 km
  ❌ 王五: 绕路比 2.84 超过上限 2.5，顺路程度不足，不建议拼单

🍔 麦顺路 · 拼单卡片
🧍 张三（发起人）  配送费: ¥9.0 → ¥4.5（省 50.0%）
🧍 赵六（伙伴）    配送费: ¥9.0 → ¥4.5（省 50.0%）
顺路度: 1.00（深度顺路）
骑手一趟总里程: 0.90 km
派单建议: 先送赵六，再送张三
配送费合计: ¥9.0（各自下单为 ¥18.0）
```

完整运行输出见 [examples/demo_output.md](examples/demo_output.md)。

## 🧠 核心算法

```
                拼单墙（附近正在点单的人）
                        │ 顺路度撮合
                        ▼
 ┌────────────┐  ① 同一门店   ┌──────────┐  顺序无关绕路比
 │ 发起人订单  │ ───────────▶ │ 撮合引擎  │  r = min(两种送餐顺序) / max(两段直达)
 └────────────┘  ② 2km 围栏   │ (matcher) │     r ≤ 1.3 深度顺路 … r > 2.5 拒绝
 ┌────────────┐  ③ 30min 窗口 └────┬─────┘
 │ 伙伴订单    │ ───────────▶      ▼  对称分摊（Shapley）
 └────────────┘              拼单卡片 + 派单建议
```

**顺序无关的顺路度（绕路比）**：骑手有两种送法（先送 A 或先送 B），取更短的一种 L，再除以"本来就要跑的那段"（两者中更远的直达距离）：

```
r = min( 门店→A + A→B , 门店→B + B→A ) / max( 门店→A , 门店→B )
```

r = 1.0 表示一方恰好在另一方的必经之路上（零绕路）；r > 2.5 拒绝。该公式对 A/B **完全对称**——谁是发起人不影响判定（有专门的单测守护这一性质）。

| 绕路比 r | 档位 | 双方各付（以 ¥9 为例） |
| --- | --- | --- |
| ≤ 1.3 | 深度顺路 | ¥4.5 ~ ¥4.95（省 45%~50%） |
| ≤ 1.8 | 中度顺路 | ¥4.95 ~ ¥5.4（省 40%~45%） |
| ≤ 2.5 | 轻度顺路 | ¥5.4 ~ ¥5.85（省 35%~40%） |
| > 2.5 | ❌ 拒绝 | 不是顺路，是专程 |

**对称分摊**：拼单能否成立对双方的贡献是对称的（缺谁都拼不成），因此按合作博弈的 Shapley 值，省下的配送费**五五分**。三条硬保证由构造直接成立（非事后校验）：① 任何一方永远不会超过单人价；② 双方省得一样多，谁先发起谁不吃亏，不存在"等着别人发起"的博弈死局；③ 平台单趟计收 ¥9.0~¥11.7，高于单订 ¥9。

## 📦 安装方法

本项目**零第三方依赖**，Python 3.9 及以上即可运行，**无需 pip install**。三种用法任选其一：

**方式一 · 获取源码（最快看到效果）**

```bash
# 方式 A：Git 克隆
git clone https://github.com/Mrezzz0822/mcd-pindan-skill.git
cd mcd-pindan-skill

# 方式 B：GitHub 页面点 Code → Download ZIP，解压后进入目录
```

无需安装任何依赖，直接即可运行（`requirements.txt` 仅为说明性文件，无内容需安装）：

```bash
python demo.py                      # 端到端演示（拼单墙场景）
python -m unittest discover tests -v # 自检：20 个用例应全部通过
```

**方式二 · 作为 Agent Skill 使用（推荐）**

把本仓库的 `SKILL.md` 复制到你的 Agent 技能目录（WorkBuddy：左侧栏【专家·技能·连接器】→ 技能 → 导入），或直接把整个仓库目录作为技能文件夹导入；再按「在 Agent 中使用」一节配置好麦当劳 MCP 即可。

**方式三 · 作为 Python 库调用**

把 `src/` 目录复制到你的工程中，直接 `from src.matcher import ...`（见下方「使用示例」）。

## 🧩 使用示例

**示例 1 · 命令行端到端演示**

```bash
python demo.py
```

输出片段（完整见 [examples/demo_output.md](examples/demo_output.md)）：

```
  ✅ 赵六: 绕路比 1.00 → 深度顺路，一趟总里程 0.90 km
  ❌ 王五: 绕路比 2.84 超过上限 2.5，顺路程度不足，不建议拼单
```

**示例 2 · Python API（拼单墙撮合 → 成团 → 分摊 → 拼单卡片）**

```python
from src.models import GeoPoint, NearbyOrder, Party, PinSession, PinStatus, PinWall
from src.matcher import rank_candidates, evaluate
from src.fee import split_fee, render_share_card

store = GeoPoint("麦当劳(北京中关村大街餐厅)", 39.98390, 116.31630)
wall = PinWall(
    store=store,
    base_delivery_fee=9.0,   # 实际由 calculate-price 返回
    initiator=Party("initiator", "张三",
                    GeoPoint("海淀大街3号 互联网金融中心", 39.98390, 116.305749), 42.5),
)
wall.add_orders([
    NearbyOrder("赵六", GeoPoint("丹棱街 甲1号", 39.98390, 116.310438), 28.0),
    NearbyOrder("王五", GeoPoint("中关村大街27号", 39.98390, 116.32600), 50.0),
])

# 拼单墙：候选按顺路程度排序
for order, result in rank_candidates(wall):
    flag = "✅" if result.ok else "❌"
    print(f"  {flag} {order.display_name}: 绕路比 {result.detour_ratio:.2f} "
          f"{result.tier if result.ok else result.reason}")

# 与最顺路的伙伴成团
best = rank_candidates(wall)[0][0]
session = PinSession(
    store=store, base_delivery_fee=9.0,
    initiator=wall.initiator,
    partner=Party("partner", best.display_name, best.destination, best.order_amount),
)
session.status = PinStatus.WAITING_PARTNER
evaluate(session)
print(render_share_card(session, split_fee(session)))
```

运行结果：

```
  ✅ 赵六: 绕路比 1.00 深度顺路
  ❌ 王五: 绕路比 2.84 超过上限 2.5，顺路程度不足，不建议拼单

🍔 麦顺路 · 拼单卡片
🧍 张三（发起人）  配送费: ¥9.0 → ¥4.5（省 50.0%）
🧍 赵六（伙伴）    配送费: ¥9.0 → ¥4.5（省 50.0%）
顺路度: 1.00（深度顺路）
骑手一趟总里程: 0.90 km
派单建议: 先送赵六，再送张三
配送费合计: ¥9.0（各自下单为 ¥18.0）
```

**示例 3 · 在 Agent 中对话使用**

配置好 MCP 后，直接对 Agent 说：

> "帮我看看附近有没有人一起点麦当劳，拼个配送费"

Agent 会自行调用麦当劳 MCP 完成选址、选品、真实配送费计算，再用本仓库算法完成撮合、分摊与派单建议。

## 🚀 在 Agent 中使用

### 跑 Demo（零依赖）

见上文「命令行 Demo」，纯 Python 标准库，无需 pip install。

### 在 Agent（WorkBuddy / Cherry Studio / Cursor 等）中使用

1. 到 [open.mcd.cn/mcp](https://open.mcd.cn/mcp) 申请麦当劳 MCP Token
2. 在客户端添加 MCP Server（参考仓库根目录 `mcp-config.example.json`，仅环境变量占位符，勿硬编码 Token）
3. 把本仓库的 `SKILL.md` 作为 Skill 导入（或直接把 `src/` 交给 Agent 的代码执行环境）
4. 对 Agent 说：**"帮我看看附近有没有人一起点麦当劳，拼个配送费"**

Agent 会调用麦当劳 MCP 完成选址、选品、真实配送费计算，再用本仓库算法完成撮合、分摊与派单建议。完整调用流程见 [MCP_INTEGRATION.md](MCP_INTEGRATION.md)。

### 跑测试

```bash
python -m unittest discover tests -v   # 20 个用例：地理 / 撮合 / 分摊 / 拼单墙
```

## 👥 目标用户

| 用户 | 场景 |
| --- | --- |
| 写字楼上班族 | 下午和隔壁楼同事拼单，¥9 配送费变 ¥4.5，转发一张卡片就成团 |
| 小区住户 | 晚上和邻居拼单，骑手一趟送两户 |
| 学生宿舍 | 同园区不同楼栋，拼单后配送费几乎可忽略 |
| 麦当劳运营 | 自配送场景下的合单调度信号：撮合引擎输出"谁和谁合并、先送谁、绕路多少"，单趟履约成本被两单摊薄，且合并配送费高于单订收入 |

## 📁 项目结构

```
mcd-pindan-skill/
├── SKILL.md                  # Skill 定义：触发场景 + Agent 工作流
├── MCP_INTEGRATION.md        # MCP 工具使用说明与调用流程
├── CONTEST_DECLARATION.md    # 参赛声明（官方模板，未改动）
├── mcp-config.example.json   # 脱敏 MCP 配置示例（仅环境变量占位符）
├── workbuddy.md              # WorkBuddy 开发对话上下文（专项奖励核验）
├── demo.py                   # 零依赖端到端演示（拼单墙场景）
├── demo/
│   └── index.html            # 在线可视化演示（拖动点位，双击即开）
├── src/
│   ├── geo.py                # haversine 距离 + geohash 网格（拼单墙粗筛）
│   ├── models.py             # 拼单墙 / 拼单会话数据模型
│   ├── matcher.py            # 三重匹配 + 顺序无关绕路比 + 墙上撮合排序
│   └── fee.py                # 合并配送费、对称分摊与拼单卡片
├── tests/                    # 20 个单元测试（unittest，零依赖）
└── examples/
    └── demo_output.md        # Demo 实际运行输出
```

## ⚠️ 边界与声明

- 本作品是比赛创意 Demo，**非麦当劳官方产品**。撮合结果与分摊金额为算法测算，实际结算以麦当劳官方渠道为准
- **坐标来源**：麦当劳 MCP 暂无地理编码工具，经纬度由用户在手机地图上长按复制提供（详见 MCP_INTEGRATION.md 第 5 节），算法使用 haversine 直线距离近似真实路网（城市路网通常有 ±30% 偏差，接入路径规划 API 可精确化）
- **拼单墙数据**：当前版本由"发起人 + 主动加入的伙伴"构成（隐私友好，不读取陌生人订单）；面向平台的版本中，墙的候选来自同一门店的实时订单流（麦乐送自配送，平台侧本就掌握该数据），本仓库的 `PinWall` 即其最小数据模型
- 地址仅用于距离计算，卡片中只展示楼宇/小区级脱敏名称

## ⭐ 支持一下

本项目参加 **麦当劳程序员创意开发大赛**，榜单按 GitHub Star 数排名，统计截止 **2026-10-25 23:59**。

如果麦顺路的思路对你有启发，麻烦点一下右上角 **Star ⭐** —— 这是对本作品最直接的支持，也是它能否进榜的唯一变量。

同样欢迎：开 Issue 聊聊绕路比阈值 2.5 该怎么定、Fork 一份改成你所在城市的版本、或转给那个每天点麦乐送的同事。

## 📄 License

MIT（见 [LICENSE](LICENSE)）
