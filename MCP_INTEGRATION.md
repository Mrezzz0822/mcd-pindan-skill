# MCP 集成说明（MCP_INTEGRATION.md）

本项目基于**麦当劳中国官方 MCP Server**（`https://mcp.mcd.cn`，Streamable HTTP 协议）开发。本文档说明实际使用的 Server、Tool、调用流程与业务价值。

## 1. MCP Server 信息

| 项目 | 内容 |
| --- | --- |
| Server 名称 | `mcd-mcp` |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权方式 | `Authorization: Bearer ${MCD_MCP_TOKEN}`（环境变量占位，Token 需到 [open.mcd.cn/mcp](https://open.mcd.cn/mcp) 申请） |
| 服务提供方 | 麦当劳中国（M-China） |

脱敏配置示例见仓库根目录 `mcp-config.example.json`（仅环境变量占位符，无真实凭证）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${MCD_MCP_TOKEN}"
      }
    }
  }
}
```

## 2. 实际使用的 Tool 清单

以下 Tool 均已对照官方工具表（M-China/mcd-mcp-server README）逐一核实存在：

| 阶段 | Tool | 用途 | 在本项目中的角色 |
| --- | --- | --- | --- |
| 时间基准 | `now-time-info` | 获取当前时间 | 计算拼单 30 分钟窗口的到期时刻 |
| 地址 | `delivery-query-addresses` | 查询可配送地址列表 | 发起人选择/确认配送地址 |
| 地址 | `delivery-create-address` | 新增配送地址 | 无可用地址时补充 |
| 门店 | `delivery-query-stores` | 查询可配送门店 | 确定拼单锚点门店（双方必须同一门店） |
| 选品 | `query-meals` / `query-meal-detail` | 查询菜单与套餐详情 | 协助双方完成选品 |
| **定价** | `calculate-price` | 计算商品价格、**配送费**、优惠及应付总价 | **核心输入**：返回的单人配送费是拼单折扣的基准 `base_delivery_fee` |
| 下单 | `create-order` | 创建订单并返回支付链接 | 拼单达成后，双方各自创建自己的订单（派单建议写入订单备注） |
| 履约 | `query-order` | 查询订单与配送状态 | 向双方同步 rider 配送进度 |
| 兜底 | `cancel-order` | 取消订单 | 伙伴超时未确认时，发起人取消拼单相关订单 |

## 3. 调用流程

```
发起人: "附近有人一起点麦当劳吗？拼个配送费"
   │
   ├─▶ now-time-info                    # 建立时间基准
   ├─▶ delivery-query-addresses         # 选地址（或 delivery-create-address）
   ├─▶ delivery-query-stores            # 确认门店（拼单锚点）
   ├─▶ query-meals / query-meal-detail  # 协助选品
   ├─▶ calculate-price                  # ★ 取得单人配送费 F
   ├─▶ （用户提供坐标，见第 5 节）
   ▼ 生成拼单卡片（本仓库 src/fee.py: render_share_card）
发起人转发卡片给同事/邻居（微信/群聊）
   │
   ▼ 伙伴提供地址 + 坐标后，本地算法接管（无需再调 MCP）
src/matcher.py: rank_candidates()  # 拼单墙撮合：候选按顺路程度排序
src/matcher.py: evaluate()         # 三重匹配 + 顺序无关绕路比 + 派单建议
src/fee.py: split_fee()            # F_pool = F×(1+k(r−1))，省下部分五五分
   │
   ▼ 双方确认
   ├─▶ create-order（发起人订单）   ─┐ 同一门店、各自地址
   ├─▶ create-order（伙伴订单）     ─┘ 备注写入派单建议
   └─▶ query-order × 2              # 同步配送进度
```

关键设计：**地理计算（haversine/geohash）、顺路度、撮合排序、费用分摊全部在本地 `src/` 完成**，不占用 MCP 调用配额；MCP 只负责它独有的真实数据——地址、门店、配送费、下单。

## 4. 业务价值

| 维度 | 说明 |
| --- | --- |
| 用户价值 | 单人点麦乐送配送费常达客单价 20%+；拼单成团后双方各省 35%~50%，且对称分摊保证谁发起谁不吃亏；拼单墙让"附近谁在点"可见，成团像拼多多一样简单 |
| 平台价值 | **麦乐送为麦当劳自配送**，平台侧本就掌握同一门店的实时订单流；撮合引擎输出的「谁和谁合并、先送谁、绕路多少」可直接作为合单调度信号。骑手单趟多带一单，履约边际成本近乎零；合并配送费（F~1.3F）高于单订收入 F——用户少付、平台多赚、骑手不多跑，三方共赢 |
| 模式差异 | 与「拼好饭」拼餐费不同，本方案只分摊履约成本，不动商品价格体系，对品牌与价格冲击最小 |
| 隐私合规 | 不读取陌生人订单流；拼单墙候选由"转发卡片 + 主动加入"构成，地址仅参与距离计算并做楼宇级脱敏；面向平台的版本中墙数据留在平台侧，本仓库 `PinWall` 即其最小数据模型 |

## 5. 数据来源边界（如实声明）

| 数据 | 来源 | 说明 |
| --- | --- | --- |
| 门店名称 / 可配送门店 | MCP `delivery-query-stores` | 官方实时数据 |
| 配送费基准 F | MCP `calculate-price` | 官方实时数据 |
| 菜单 / 价格 / 下单 | MCP `query-meals` 等 | 官方实时数据 |
| **三方坐标** | **用户提供** | 麦当劳 MCP 暂无地理编码（geocoding）工具；由用户在手机地图 App 长按位置复制坐标（SKILL.md 第二步）。接入高德/百度地理编码 API 可自动化的部分已列入 Roadmap |
| 距离 | 本地 haversine | 直线距离近似真实路网，城市路网通常有 ±30% 偏差；接入路径规划 API 可精确化 |

## 6. 注意事项

- Token 通过环境变量 `MCD_MCP_TOKEN` 注入，仓库内不出现任何真实凭证（`mcp-config.example.json` 仅占位符）
- MCP 限流 600 次/分钟/Token，本项目 MCP 调用量极小（每单约 8~10 次），无压力；撮合算法全在本地，不占配额
- 餐品价格、配送费、供应状态以 `calculate-price` 实时返回为准，Demo 中的 ¥9 仅为常见示例值
