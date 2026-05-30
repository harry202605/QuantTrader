from datetime import datetime, date
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from .models import Execution, ExecutionSignal, RiskRule, RiskAlert, ExecutionLog
from .schemas import (
    ExecutionCreate, ExecutionUpdate, ExecutionSignalCreate,
    RiskRuleCreate, RiskRuleUpdate, RiskAlertCreate, RiskAlertUpdate,
    ExecutionLogCreate, MockKlineData
)


async def _mock_get_strategy_code(strategy_id: int) -> Tuple[str, str]:
    """Mock 调用模块3获取策略代码和名称"""
    mock_strategies = {
        1: ("双均线策略", "def on_bar(data, context):\n    if data['ma5'] > data['ma10']:\n        context.buy()"),
        2: ("MACD策略", "def on_bar(data, context):\n    if data['macd'] > data['signal']:\n        context.buy()"),
        3: ("RSI策略", "def on_bar(data, context):\n    if data['rsi'] < 30:\n        context.buy()"),
    }
    return mock_strategies.get(strategy_id, ("默认策略", "def on_bar(data, context): pass"))


async def _mock_get_kline(symbol: str, days: int = 30) -> List[MockKlineData]:
    """Mock 调用模块1获取K线数据"""
    mock_data = []
    base_price = 10.0
    for i in range(days):
        d = date(2024, 1, 1).toordinal() + i
        dt = date.fromordinal(d)
        change = (i % 7 - 3) * 0.2
        close = round(base_price + change, 2)
        mock_data.append(MockKlineData(
            date=dt.strftime("%Y-%m-%d"),
            open=round(close - 0.1, 2),
            high=round(close + 0.2, 2),
            low=round(close - 0.2, 2),
            close=close,
            volume=100000 + i * 1000,
            ma5=round(base_price + (i % 5 - 2) * 0.1, 2),
            ma10=round(base_price + (i % 10 - 5) * 0.05, 2),
            ma20=round(base_price, 2),
        ))
        base_price = close
    return mock_data


async def _mock_place_order(signal: ExecutionSignalCreate) -> Tuple[str, str]:
    """Mock 调用模块2下单"""
    order_id = f"MOCK_ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return order_id, "submitted"


async def _check_risk_rules(signal: ExecutionSignalCreate, db: AsyncSession) -> Tuple[bool, Optional[str]]:
    """检查风控规则"""
    result = await db.execute(select(RiskRule).where(RiskRule.enabled == True))
    rules = result.scalars().all()

    for rule in rules:
        if rule.rule_type == "single_stock_limit":
            max_qty = rule.params.get("max_quantity", 10000)
            if signal.quantity > max_qty:
                return False, f"单品种数量超限: {signal.quantity} > {max_qty}"

        elif rule.rule_type == "daily_loss_limit":
            max_loss = rule.params.get("max_loss_pct", 5.0)
            today = date.today()
            result = await db.execute(
                select(func.sum(ExecutionSignal.pnl))
                .where(
                    and_(
                        ExecutionSignal.execution_id == signal.execution_id,
                        func.date(ExecutionSignal.created_at) == today,
                        ExecutionSignal.pnl < 0,
                    )
                )
            )
            today_loss = result.scalar() or 0
            if abs(today_loss) > max_loss * 10000:
                return False, f"单日亏损超限: {today_loss}"

        elif rule.rule_type == "position_limit":
            max_pct = rule.params.get("max_position_pct", 30.0)
            pass

    return True, None


async def create_execution(db: AsyncSession, data: ExecutionCreate) -> Execution:
    """创建策略执行实例"""
    strategy_name, _ = await _mock_get_strategy_code(data.strategy_id)
    execution = Execution(
        strategy_id=data.strategy_id,
        strategy_name=data.strategy_name or strategy_name,
        account_id=data.account_id,
        status="running",
        start_time=datetime.now(),
        params=data.params,
        remark=data.remark,
    )
    db.add(execution)
    await db.flush()

    log = ExecutionLog(
        execution_id=execution.id,
        level="info",
        category="execution",
        message=f"策略执行已启动: {execution.strategy_name}",
    )
    db.add(log)

    await db.commit()
    await db.refresh(execution)
    return execution


async def get_execution_list(db: AsyncSession, status: Optional[str] = None, strategy_id: Optional[int] = None) -> List[Execution]:
    """获取执行实例列表"""
    query = select(Execution).order_by(Execution.created_at.desc())
    if status:
        query = query.where(Execution.status == status)
    if strategy_id:
        query = query.where(Execution.strategy_id == strategy_id)
    result = await db.execute(query)
    return result.scalars().all()


async def get_execution_list_paginated(
    db: AsyncSession,
    status: Optional[str] = None,
    strategy_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Execution], int]:
    """获取执行实例列表（分页）"""
    query = select(Execution).order_by(Execution.created_at.desc())
    if status:
        query = query.where(Execution.status == status)
    if strategy_id:
        query = query.where(Execution.strategy_id == strategy_id)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all(), total


async def get_execution(db: AsyncSession, execution_id: int) -> Optional[Execution]:
    """获取执行实例详情"""
    result = await db.execute(select(Execution).where(Execution.id == execution_id))
    return result.scalar_one_or_none()


async def update_execution(db: AsyncSession, execution_id: int, data: ExecutionUpdate) -> Optional[Execution]:
    """更新执行实例"""
    execution = await get_execution(db, execution_id)
    if not execution:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(execution, field, value)

    log = ExecutionLog(
        execution_id=execution_id,
        level="info",
        category="execution",
        message=f"策略执行状态更新: {data.status}",
        details=data.model_dump(),
    )
    db.add(log)

    await db.commit()
    await db.refresh(execution)
    return execution


async def stop_execution(db: AsyncSession, execution_id: int) -> Optional[Execution]:
    """停止执行实例"""
    execution = await get_execution(db, execution_id)
    if not execution:
        return None

    execution.status = "stopped"
    execution.end_time = datetime.now()

    log = ExecutionLog(
        execution_id=execution_id,
        level="info",
        category="execution",
        message="策略执行已停止",
    )
    db.add(log)

    await db.commit()
    await db.refresh(execution)
    return execution


async def pause_execution(db: AsyncSession, execution_id: int) -> Optional[Execution]:
    """暂停执行实例"""
    execution = await get_execution(db, execution_id)
    if not execution:
        return None

    execution.status = "paused"

    log = ExecutionLog(
        execution_id=execution_id,
        level="warning",
        category="execution",
        message="策略执行已暂停",
    )
    db.add(log)

    await db.commit()
    await db.refresh(execution)
    return execution


async def resume_execution(db: AsyncSession, execution_id: int) -> Optional[Execution]:
    """恢复执行实例"""
    execution = await get_execution(db, execution_id)
    if not execution:
        return None

    execution.status = "running"

    log = ExecutionLog(
        execution_id=execution_id,
        level="info",
        category="execution",
        message="策略执行已恢复",
    )
    db.add(log)

    await db.commit()
    await db.refresh(execution)
    return execution


async def generate_mock_signal(db: AsyncSession, execution_id: int) -> Optional[ExecutionSignal]:
    """Mock 生成交易信号（模拟策略运行）"""
    execution = await get_execution(db, execution_id)
    if not execution or execution.status != "running":
        return None

    kline_data = await _mock_get_kline("000001.SZ", days=10)
    latest = kline_data[-1]

    direction = "buy" if latest.ma5 > latest.ma10 else "sell"
    signal_data = ExecutionSignalCreate(
        execution_id=execution_id,
        strategy_id=execution.strategy_id,
        symbol="000001.SZ",
        symbol_name="平安银行",
        direction=direction,
        signal_price=latest.close,
        quantity=100,
        order_type="limit",
        reason=f"MA5({latest.ma5}) {'上穿' if direction == 'buy' else '下穿'} MA10({latest.ma10})",
    )

    risk_passed, risk_reason = await _check_risk_rules(signal_data, db)

    signal = ExecutionSignal(
        **signal_data.model_dump(),
        risk_passed=risk_passed,
        risk_reason=risk_reason,
    )

    if risk_passed:
        order_id, order_status = await _mock_place_order(signal_data)
        signal.order_id = order_id
        signal.order_status = order_status
        signal.filled_price = latest.close
        signal.filled_quantity = 100
        signal.pnl = 0.0

    db.add(signal)

    execution.total_signals += 1
    if risk_passed:
        execution.total_orders += 1

    log = ExecutionLog(
        execution_id=execution_id,
        level="info" if risk_passed else "warning",
        category="signal",
        message=f"{'产生' if risk_passed else '风控拒绝'}交易信号: {direction} {signal_data.symbol} @ {latest.close}",
        details={"risk_passed": risk_passed, "risk_reason": risk_reason},
    )
    db.add(log)

    await db.commit()
    await db.refresh(signal)
    return signal


async def get_signals(db: AsyncSession, execution_id: Optional[int] = None, limit: int = 100) -> List[ExecutionSignal]:
    """获取交易信号列表"""
    query = select(ExecutionSignal).order_by(ExecutionSignal.created_at.desc())
    if execution_id:
        query = query.where(ExecutionSignal.execution_id == execution_id)
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_signals_paginated(
    db: AsyncSession,
    execution_id: Optional[int] = None,
    risk_passed: Optional[bool] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[ExecutionSignal], int]:
    """获取交易信号列表（分页）"""
    query = select(ExecutionSignal).order_by(ExecutionSignal.created_at.desc())
    if execution_id:
        query = query.where(ExecutionSignal.execution_id == execution_id)
    if risk_passed is not None:
        query = query.where(ExecutionSignal.risk_passed == risk_passed)
    if start_date:
        query = query.where(func.date(ExecutionSignal.created_at) >= start_date)
    if end_date:
        query = query.where(func.date(ExecutionSignal.created_at) <= end_date)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all(), total


async def create_risk_rule(db: AsyncSession, data: RiskRuleCreate) -> RiskRule:
    """创建风控规则"""
    rule = RiskRule(**data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def get_risk_rules(db: AsyncSession, enabled: Optional[bool] = None) -> List[RiskRule]:
    """获取风控规则列表"""
    query = select(RiskRule).order_by(RiskRule.created_at.desc())
    if enabled is not None:
        query = query.where(RiskRule.enabled == enabled)
    result = await db.execute(query)
    return result.scalars().all()


async def get_risk_rule(db: AsyncSession, rule_id: int) -> Optional[RiskRule]:
    """获取风控规则详情"""
    result = await db.execute(select(RiskRule).where(RiskRule.id == rule_id))
    return result.scalar_one_or_none()


async def update_risk_rule(db: AsyncSession, rule_id: int, data: RiskRuleUpdate) -> Optional[RiskRule]:
    """更新风控规则"""
    rule = await get_risk_rule(db, rule_id)
    if not rule:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_risk_rule(db: AsyncSession, rule_id: int) -> bool:
    """删除风控规则"""
    rule = await get_risk_rule(db, rule_id)
    if not rule:
        return False
    await db.delete(rule)
    await db.commit()
    return True


async def create_risk_alert(db: AsyncSession, data: RiskAlertCreate) -> RiskAlert:
    """创建风控告警"""
    alert = RiskAlert(**data.model_dump())
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


async def get_risk_alerts(
    db: AsyncSession,
    execution_id: Optional[int] = None,
    acknowledged: Optional[bool] = None,
    limit: int = 100,
) -> List[RiskAlert]:
    """获取风控告警列表"""
    query = select(RiskAlert).order_by(RiskAlert.created_at.desc())
    if execution_id:
        query = query.where(RiskAlert.execution_id == execution_id)
    if acknowledged is not None:
        query = query.where(RiskAlert.acknowledged == acknowledged)
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_risk_alerts_paginated(
    db: AsyncSession,
    execution_id: Optional[int] = None,
    level: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[RiskAlert], int]:
    """获取风控告警列表（分页）"""
    query = select(RiskAlert).order_by(RiskAlert.created_at.desc())
    if execution_id:
        query = query.where(RiskAlert.execution_id == execution_id)
    if level:
        query = query.where(RiskAlert.severity == level)
    if acknowledged is not None:
        query = query.where(RiskAlert.acknowledged == acknowledged)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all(), total


async def acknowledge_alert(db: AsyncSession, alert_id: int, acknowledged_by: str = "system") -> Optional[RiskAlert]:
    """确认告警"""
    result = await db.execute(select(RiskAlert).where(RiskAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        return None
    alert.acknowledged = True
    alert.acknowledged_at = datetime.now()
    alert.acknowledged_by = acknowledged_by
    await db.commit()
    await db.refresh(alert)
    return alert


async def get_execution_logs(db: AsyncSession, execution_id: int, limit: int = 200) -> List[ExecutionLog]:
    """获取执行日志"""
    query = (
        select(ExecutionLog)
        .where(ExecutionLog.execution_id == execution_id)
        .order_by(ExecutionLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


async def get_execution_logs_paginated(
    db: AsyncSession,
    execution_id: int,
    level: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[ExecutionLog], int]:
    """获取执行日志（分页）"""
    query = select(ExecutionLog).where(ExecutionLog.execution_id == execution_id).order_by(ExecutionLog.created_at.desc())
    if level:
        query = query.where(ExecutionLog.level == level)
    if start_date:
        query = query.where(func.date(ExecutionLog.created_at) >= start_date)
    if end_date:
        query = query.where(func.date(ExecutionLog.created_at) <= end_date)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all(), total


async def get_execution_status(db: AsyncSession):
    """获取执行状态概览"""
    today = date.today()

    result = await db.execute(select(func.count(Execution.id)).where(Execution.status == "running"))
    running_count = result.scalar() or 0

    result = await db.execute(select(func.count(Execution.id)).where(Execution.status == "paused"))
    paused_count = result.scalar() or 0

    result = await db.execute(select(func.count(Execution.id)).where(Execution.status == "stopped"))
    stopped_count = result.scalar() or 0

    result = await db.execute(
        select(func.sum(ExecutionSignal.pnl))
        .where(func.date(ExecutionSignal.created_at) == today)
    )
    today_pnl = float(result.scalar() or 0)

    result = await db.execute(
        select(func.count(RiskAlert.id)).where(RiskAlert.acknowledged == False)
    )
    active_alerts = result.scalar() or 0

    result = await db.execute(
        select(func.count(ExecutionSignal.id))
        .where(func.date(ExecutionSignal.created_at) == today)
    )
    total_signals_today = result.scalar() or 0

    return {
        "running_count": running_count,
        "paused_count": paused_count,
        "stopped_count": stopped_count,
        "today_pnl": today_pnl,
        "active_alerts": active_alerts,
        "total_signals_today": total_signals_today,
    }


async def init_default_risk_rules(db: AsyncSession):
    """初始化默认风控规则"""
    default_rules = [
        {
            "rule_type": "single_stock_limit",
            "rule_name": "单品种最大持仓限制",
            "params": {"max_quantity": 10000, "max_position_pct": 30.0},
            "action": "reject_signal",
            "description": "单只股票最大持仓10000股或总资金30%",
        },
        {
            "rule_type": "daily_loss_limit",
            "rule_name": "单日最大亏损限制",
            "params": {"max_loss_pct": 5.0, "max_loss_amount": 50000},
            "action": "pause_execution",
            "description": "单日亏损超过5%或5万元暂停交易",
        },
        {
            "rule_type": "single_trade_loss",
            "rule_name": "单笔亏损限制",
            "params": {"max_loss_pct": 2.0, "stop_loss_pct": 5.0},
            "action": "alert_only",
            "description": "单笔交易亏损超过2%告警，超过5%强制平仓",
        },
        {
            "rule_type": "max_drawdown",
            "rule_name": "最大回撤限制",
            "params": {"max_drawdown_pct": 15.0},
            "action": "pause_execution",
            "description": "账户最大回撤超过15%停止所有策略",
        },
        {
            "rule_type": "trading_frequency",
            "rule_name": "交易频率限制",
            "params": {"max_daily_trades": 50, "max_hourly_trades": 10},
            "action": "reject_signal",
            "description": "单日最多50笔交易，单小时最多10笔",
        },
    ]

    for rule_data in default_rules:
        existing = await db.execute(
            select(RiskRule).where(RiskRule.rule_type == rule_data["rule_type"])
        )
        if existing.scalar_one_or_none():
            continue
        rule = RiskRule(**rule_data)
        db.add(rule)

    await db.commit()
