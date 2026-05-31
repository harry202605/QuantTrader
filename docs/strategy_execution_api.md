# 模块4: 策略执行与实时风控 - 对外接口文档

**模块负责人**：模块4负责人

**文档目的**：给其他模块负责人看，了解本模块能提供什么服务

---

## 一、整体业务流程与数据流

### 1.1 完整业务链路图

```
┌─────────────────┐
│ 模块1: 行情数据  │
│   api_data       │
└───────┬─────────┘
        │
        │ 【模块4调用模块1】
        │ 策略运行时，持续获取K线/Ticker
        ▼
┌───────────────────────────────┐
│ 模块4: 策略执行与风控（本模块） │
│     strategy_execution       │
│  ┌───────────────────────┐
│  │  策略执行引擎      │
│  │  - 加载策略代码    │◄──────┐
│  │  - 驱动策略运行    │       │
│  │  - 产生交易信号    │       │
│  └─────────┬─────────────┘       │
│            │               │ 【模块4调用模块3】
│  ┌─────────▼─────────────┐       │ 启动时拉取策略代码
│  │  风控引擎              │       │
│  │  - 事前风控检查       │       │
│  │  - 事中风控监控       │       │
│  │  - 产生告警          │       │
│  └─────────┬─────────────┘       │
└────────────┼──────────────┘       │
             │                      │
    ┌────────┴────────┐             │
    │                 │             │
    ▼                 ▼             │
┌─────────────┐ ┌─────────────┐     │
│ 模块2: 账户  │ │ 模块5: 复盘  │     │
│  交易        │ │  分析        │     │
└─────────────┘ └─────────────┘     │
                                      │
                            ┌─────────┴─────────┐
                            │ 模块3: 策略引擎    │
                            │ strategy_engine   │
                            │ - 策略CRUD         │
                            │ - 代码编辑         │
                            │ - 启动/停止按钮    │
                            └─────────┬─────────┘
                                      │
                                      │ 【模块3调用模块4】
                                      │ 用户点击启动按钮时
                                      ▼
                           （回调到模块4的start接口）

┌─────────────┐
│ 模块6: 回放  │
│  模拟执行    │
└─────────────┘
```

### 1.2 数据流方向

```
数据流入（本模块←其他模块）：
  模块1 → 本模块：K线数据、Ticker行情（策略运行输入）
  模块2 → 本模块：持仓数据、订单状态（风控计算用）
  模块3 → 本模块：策略代码、参数配置（执行用）
  模块6 → 本模块：历史K线数据（模拟执行）

数据流出（本模块→其他模块）：
  本模块 → 模块2：下单请求（风控通过后）
  本模块 → 模块5：执行记录、信号记录、告警记录
  本模块 → 模块6：模拟执行结果
  本模块 → 前端：执行状态、信号、告警、日志
```

---

## 二、本模块对外提供的接口

**路由前缀**: `/api/execution`

---

### 2.1 执行实例相关接口

---

#### 接口1: 启动策略执行

**其他模块调用场景**：模块3（策略引擎）在策略启动时调用

```http
POST /api/execution/start
```

**请求体**:
```json
{
  "strategy_id": 1,      // 必需：策略ID（来自模块3）
  "account_id": 1          // 必需：账户ID（来自模块2）
}
```

**返回数据**:
```json
{
  "success": true,
  "data": {
    "execution_id": 1,          // 执行实例ID（重要！后续接口都要用这个）
    "strategy_id": 1,
    "status": "running",         // running / stopped / paused / error
    "started_at": "2024-01-15 09:30:00"
  },
  "message": "策略执行已启动"
}
```

**使用说明**:
- 创建一个新的执行实例，开始运行策略
- 返回的 `execution_id` 是后续所有接口的关键关联ID

---

#### 接口2: 停止策略执行

**其他模块调用场景**：模块3停止策略时调用

```http
POST /api/execution/{execution_id}/stop
```

**路径参数**:
- `execution_id`: 执行实例ID

**返回数据**:
```json
{
  "success": true,
  "data": {
    "execution_id": 1,
    "status": "stopped",
    "stopped_at": "2024-01-15 15:00:00",
    "final_pnl": 15000.00       // 最终盈亏
  },
  "message": "策略执行已停止"
}
```

---

#### 接口3: 暂停/恢复策略执行

```http
POST /api/execution/{execution_id}/pause
POST /api/execution/{execution_id}/resume
```

**使用场景**:
- 风控触发时自动暂停
- 人工干预暂停/恢复

---

#### 接口4: 获取执行实例列表

**其他模块调用场景**：模块5复盘时查询

```http
GET /api/execution/list
```

**查询参数**（可选）:
- `strategy_id`: 按策略ID过滤
- `status`: 按状态过滤 (running/stopped/paused)
- `page`: 页码
- `page_size`: 每页数量

**返回数据**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 1,
        "strategy_id": 1,
        "strategy_name": "双均线策略",
        "account_id": 1,
        "status": "running",
        "started_at": "2024-01-15 09:30:00",
        "pnl": 8500.00
      }
    ],
    "total": 10,
    "page": 1,
    "page_size": 20
  }
}
```

---

#### 接口5: 获取执行实例详情

**其他模块调用场景**：模块5复盘分析时查询详细信息

```http
GET /api/execution/{execution_id}
```

**返回数据**:
```json
{
  "success": true,
  "data": {
    "id": 1,
    "strategy_id": 1,
    "strategy_name": "双均线策略",
    "account_id": 1,
    "status": "running",
    "started_at": "2024-01-15 09:30:00",
    "pnl": 8500.00,
    "signals_count": 25,           // 产生信号总数
    "risk_alerts_count": 2,         // 风控告警数
    "current_drawdown": 2.3        // 当前回撤
  },
  "message": "操作成功"
}
```

---

### 2.2 交易信号相关接口

---

#### 接口6: 获取执行信号列表

**其他模块调用场景**：模块5复盘分析时查询所有信号

```http
GET /api/execution/{execution_id}/signals
```

**查询参数**（可选）:
- `risk_passed`: true/false，是否通过风控
- `start_date`: 开始日期
- `end_date`: 结束日期
- `page`: 页码
- `page_size`: 每页数量

**返回数据**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "signal_id": "SIG001",
        "symbol": "000001.SZ",
        "side": "buy",                  // buy / sell / close
        "signal_type": "entry",            // entry / exit / adjust
        "suggested_price": 10.50,
        "suggested_quantity": 1000,
        "reason": "MA5上穿MA10",          // 信号产生原因
        "risk_passed": true,             // 风控是否通过
        "risk_rejection_reason": null,   // 风控拒绝原因
        "order_submitted": true,          // 是否已提交订单到模块2
        "order_id": "ORD001",             // 模块2的订单ID
        "created_at": "2024-01-15 09:35:00"
      }
    ],
    "total": 25,
    "page": 1,
    "page_size": 20
  }
}
```

**重要字段说明**:
- `risk_passed`: true 表示风控通过，已调用了模块2的下单接口
- `order_id`: 关联模块2的订单ID（如果风控通过）

---

### 2.3 风控规则相关接口

---

#### 接口7: 获取风控规则列表

**其他模块调用场景**：任何模块查询当前生效的风控规则

```http
GET /api/execution/risk-rules
```

**查询参数**（可选）:
- `strategy_id`: 策略ID（不传返回全局规则）
- `rule_type`: 规则类型过滤

**返回数据**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "最大回撤限制",
      "rule_type": "max_drawdown",      // 规则类型
      "strategy_id": null,                 // null表示全局规则
      "threshold_json": {               // 阈值配置
        "max_drawdown_pct": 10.0
      },
      "action": "pause_execution",     // 触发动作
      "enabled": true
    }
  ]
}
```

**规则类型说明** (`rule_type`):
- `max_drawdown`: 最大回撤
- `single_stop_loss`: 单笔止损
- `position_limit`: 持仓上限
- `frequency_limit`: 频率限制
- `daily_loss`: 单日亏损

**触发动作说明** (`action`):
- `alert_only`: 仅告警
- `reject_signal`: 拒绝信号
- `pause_execution`: 暂停执行

---

### 2.4 风控告警相关接口

---

#### 接口8: 获取活跃告警

**其他模块调用场景**：首页/仪表盘展示活跃告警

```http
GET /api/execution/risk-alerts/active
```

**返回数据**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "execution_id": 1,
      "strategy_name": "双均线策略",
      "rule_type": "daily_loss",
      "level": "critical",                // warning / critical
      "message": "单日亏损已达5.2%，超过阈值5%",
      "triggered_value": 5.2,
      "threshold_value": 5.0,
      "action_taken": "pause_execution",  // 已执行的动作
      "acknowledged": false,             // 是否已确认
      "triggered_at": "2024-01-15 14:30:00"
    }
  ]
}
```

---

#### 接口9: 获取告警历史

**其他模块调用场景**：模块5复盘分析时查询

```http
GET /api/execution/risk-alerts
```

**查询参数**（可选）:
- `execution_id`: 执行实例ID
- `level`: 级别过滤
- `acknowledged`: 是否已确认
- `page`: 页码
- `page_size`: 每页数量

---

#### 接口10: 确认告警

**其他模块调用场景**：人工确认告警后调用

```http
POST /api/execution/risk-alerts/{alert_id}/acknowledge
```

**请求体**:
```json
{
  "acknowledged_by": "admin",   // 确认人
  "note": "已知晓"                // 备注（可选）
}
```

---

### 2.5 执行状态与日志接口

---

#### 接口11: 获取实时执行状态

**其他模块调用场景**：首页/仪表盘展示概览数据

```http
GET /api/execution/status
```

**返回数据**:
```json
{
  "success": true,
  "data": {
    "running_executions": 3,        // 运行中策略数
    "paused_executions": 1,         // 已暂停策略数
    "active_alert_count": 2,         // 活跃告警数
    "total_pnl_today": 15680.50,  // 今日总盈亏
    "overall_drawdown": 2.3,         // 总体回撤
    "risk_status": "normal"          // normal / warning / critical
  }
}
```

---

#### 接口12: 获取执行日志

**其他模块调用场景**：模块5复盘分析、问题排查

```http
GET /api/execution/{execution_id}/logs
```

**查询参数**（可选）:
- `level`: 日志级别 (info / warning / error)
- `start_date`: 开始日期
- `end_date`: 结束日期
- `page`: 页码
- `page_size`: 每页数量

**返回数据**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "timestamp": "2024-01-15 09:30:00",
        "level": "info",
        "message": "策略执行启动",
        "data_json": null
      }
    ],
    "total": 150,
    "page": 1,
    "page_size": 50
  }
}
```

---

## 三、本模块需要调用其他模块的接口

（给其他模块负责人看：你们需要提供这些接口给我）

---

### 3.1 需要模块1（行情数据）提供

```http
# 获取K线数据
GET /api/api-data/kline?symbol={code}&timeframe={tf}

# 获取最新行情
GET /api/api-data/ticker?symbol={code}

# 获取交易对列表
GET /api/api-data/symbols
```

**用途**：策略运行时，定时获取行情数据喂给策略

---

### 3.2 需要模块2（账户交易）提供

```http
# 下单接口（风控通过后我会调用）
POST /api/account/order
{
  "account_id": 1,
  "symbol": "000001.SZ",
  "side": "buy",
  "type": "limit",
  "price": 10.50,
  "quantity": 1000,
  "strategy_id": 1,
  "execution_id": 1        // 我会传这个给你，请存起来
}

# 查询持仓（风控计算用）
GET /api/account/positions?account_id={account_id}

# 查询订单
GET /api/account/orders?strategy_id={strategy_id}
```

**重要约定**：
- 请在你们的 order 表中增加 `execution_id` 字段，关联我的执行实例
- 请在你们的 order 表中增加 `strategy_id` 字段，关联策略ID

---

### 3.3 需要模块3（策略引擎）提供

```http
# 获取策略详情
GET /api/strategy/{strategy_id}

返回：
{
  "id": 1,
  "name": "双均线策略",
  "code": "def on_bar(data, context):...",
  "parameters_json": { ... },
  "status": "active"
}
```

**用途**：启动执行时加载策略代码和参数

---

## 四、数据结构定义

（给其他模块负责人看：我存的数据结构是这样的）

### 4.1 执行实例状态枚举

```
running   - 运行中
paused  - 已暂停
stopped - 已停止
error   - 运行错误
```

### 4.2 信号类型枚举

```
entry  - 开仓信号
exit   - 平仓信号
adjust - 调仓信号
```

### 4.3 信号方向枚举

```
buy   - 买入
sell  - 卖出
close - 平仓（清仓）
```

### 4.4 风控告警级别

```
warning  - 警告（不影响执行）
critical - 严重（可能触发暂停）
```

---

## 五、各模块协作速查表

### 5.1 谁调用我（本模块对外提供服务）

| 调用方 | 调用场景 | 触发方式 | 主要接口 |
|-------|---------|---------|---------|
| **模块3** | 用户点击「启动策略」按钮 | 用户操作触发 | `POST /execution/start` |
| **模块3** | 用户点击「停止策略」按钮 | 用户操作触发 | `POST /execution/{id}/stop` |
| **模块5** | 复盘分析查询历史数据 | 主动查询 | `GET /execution/{id}`, `GET /{id}/signals`, `GET /{id}/logs` |
| **前端** | 执行监控页面展示 | 主动查询 | 全部接口 |
| **首页/仪表盘** | 概览数据展示 | 主动查询 | `GET /execution/status`, `GET /risk-alerts/active` |

---

### 5.2 我调用谁（本模块依赖其他模块）

| 被调用方 | 调用场景 | 触发方式 | 主要接口 |
|---------|---------|---------|---------|
| **模块1** | 策略运行时获取K线数据 | 定时触发 | `GET /api-data/kline` |
| **模块1** | 策略运行时获取最新行情 | 按需触发 | `GET /api-data/ticker` |
| **模块2** | 风控通过后下单 | 信号产生触发 | `POST /account/order` |
| **模块2** | 风控检查时查询持仓 | 信号产生触发 | `GET /account/positions` |
| **模块3** | 启动策略时加载代码 | 启动时触发 | `GET /strategy/{id}` |

---

### 5.3 调用关系示意图

```
用户操作
   ↓
模块3（策略列表页）
   ↓ 【用户点击启动】
模块4（本模块） ←────────┐
   ↓ 【启动时拉取代码】    │
模块3                     │ 【双向调用】
   ↓                      │
模块4（本模块）            │
   ↓ 【运行时持续获取】    │
模块1（行情数据） ─────────┘
   ↓
模块4（本模块）
   ↓ 【风控通过后】
模块2（账户交易）
```

---



**文档版本**: v1.1
**最后更新**: 2026-05-24
