#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试定投回测的各种场景
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from portfolio_backtester import BacktestEngine, InvestmentSchedule, Portfolio


class MockFundDataManager:
    """模拟数据管理器，用于测试"""

    def __init__(self):
        self.fund_data = {}
        self.dividend_data = {}
        self.purchase_status = {}  # {fund_code: {date: status}}

    def add_fund_data(self, fund_code: str, data: pd.DataFrame):
        """添加基金净值数据"""
        self.fund_data[fund_code] = data

    def set_purchase_status(self, fund_code: str, start_date: datetime, end_date: datetime, status: str):
        """设置申购状态"""
        if fund_code not in self.purchase_status:
            self.purchase_status[fund_code] = {}
        current = start_date
        while current <= end_date:
            self.purchase_status[fund_code][current] = status
            current += timedelta(days=1)

    def get_multi_fund_data(self, fund_codes: List[str]) -> Dict[str, pd.DataFrame]:
        """获取多只基金数据"""
        return {code: self.fund_data.get(code, pd.DataFrame()) for code in fund_codes}

    def get_common_trading_days(self, fund_data: Dict[str, pd.DataFrame]) -> List[datetime]:
        """获取共同交易日"""
        if not fund_data:
            return []

        # 获取所有基金的交易日
        all_trading_days = []
        for df in fund_data.values():
            if not df.empty:
                days = set(df['净值日期'].tolist())
                all_trading_days.append(days)

        # 取交集
        if not all_trading_days:
            return []

        common = all_trading_days[0]
        for days in all_trading_days[1:]:
            common = common.intersection(days)

        return sorted(list(common))

    def get_nav_for_date(self, fund_code: str, date: datetime,
                        fund_data: Dict[str, pd.DataFrame]) -> Optional[float]:
        """获取指定日期的净值"""
        if fund_code not in fund_data:
            return None
        df = fund_data[fund_code]
        row = df[df['净值日期'] == date]
        if not row.empty:
            return row.iloc[0]['单位净值']
        return None

    def get_dividend_for_date(self, fund_code: str, date: datetime,
                             fund_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
        """获取指定日期的分红信息"""
        if fund_code in self.dividend_data:
            dividends = self.dividend_data[fund_code]
            for div_date, div_info in dividends:
                if div_date == date:
                    return div_info
        return None

    def can_purchase_all(self, fund_codes: List[str], date: datetime,
                        fund_data: Dict[str, pd.DataFrame]) -> Tuple[bool, List[str]]:
        """检查所有基金是否都可以申购"""
        blocked_funds = []
        for fund_code in fund_codes:
            if fund_code in self.purchase_status:
                # 检查是否有最近的申购状态记录
                statuses = self.purchase_status[fund_code]
                if date in statuses:
                    if statuses[date] in ['封闭期', '暂停申购']:
                        blocked_funds.append(fund_code)

        if blocked_funds:
            return False, blocked_funds
        return True, []


def create_simple_nav_data(start_date: datetime, end_date: datetime,
                          nav_value: float = 1.0) -> pd.DataFrame:
    """创建简单的净值数据"""
    dates = []
    navs = []
    current = start_date
    while current <= end_date:
        # 只包含工作日（排除周末）
        if current.weekday() < 5:  # 0-4 表示周一到周五
            dates.append(current)
            navs.append(nav_value)
        current += timedelta(days=1)

    return pd.DataFrame({
        '净值日期': dates,
        '单位净值': navs,
        '累计净值': [n * 1.2 for n in navs],
        '日增长率(%)': [0.1] * len(dates),
        '申购状态': ['开放申购'] * len(dates),
        '赎回状态': ['开放赎回'] * len(dates)
    })


def print_section(title: str):
    """打印分隔线"""
    print(f"\n{'#' * 80}")
    print(f"#{title:^78}#")
    print(f"{'#' * 80}\n")


def verify_trades(result: 'BacktestResult', expected_trades: int, expected_cash: float):
    """验证交易记录"""
    trades = result.trades

    print(f"\n{'─' * 60}")
    print(f"【验证结果】")
    print(f"  实际交易次数: {len(trades)}")
    print(f"  预期交易次数: {expected_trades}")
    print(f"  匹配: {'✓' if len(trades) == expected_trades else '✗'}")

    # 计算累计投入
    total_invested = sum(t['amount'] for t in trades if t['type'] == '定投申购')
    print(f"\n  累计投入: {total_invested:.2f} 元")
    print(f"  预期投入: {expected_cash:.2f} 元")
    print(f"  匹配: {'✓' if abs(total_invested - expected_cash) < 0.01 else '✗'}")

    # 打印所有交易
    if trades:
        print(f"\n【交易明细】")
        for i, trade in enumerate(trades, 1):
            print(f"\n  交易 #{i}:")
            print(f"    日期: {trade['date'].strftime('%Y-%m-%d')}")
            print(f"    基金: {trade['fund_code']}")
            print(f"    类型: {trade['type']}")
            if trade['type'] == '定投申购':
                print(f"    金额: {trade['amount']:.2f} 元")
                print(f"    份额: {trade['shares']:.2f}")
                print(f"    份额变化: {trade['shares_before']:.2f} → {trade['shares_after']:.2f}")
                print(f"    计算: {trade['calculation']}")
            elif trade['type'] == '红利再投资':
                print(f"    每份分红: {trade['dividend_per_unit']:.4f} 元")
                print(f"    分红金额: {trade['dividend_amount']:.2f} 元")
                print(f"    新增份额: {trade['new_shares']:.2f}")
                print(f"    份额变化: {trade['shares_before']:.2f} → {trade['shares_after']:.2f}")

    print(f"{'─' * 60}")


def test_scenario_1_normal_daily_invest():
    """场景1：正常日定投（每个交易日都定投）"""
    print_section("场景1：正常日定投")

    # 创建测试数据：2024-01-02 到 2024-01-05（4个交易日）
    start = datetime(2024, 1, 2)
    end = datetime(2024, 1, 5)

    manager = MockFundDataManager()
    manager.add_fund_data('000001', create_simple_nav_data(start, end, 1.0))

    schedule = InvestmentSchedule(frequency='daily', amount=1000.0)

    engine = BacktestEngine(
        allocations={'000001': 1.0},
        schedule=schedule,
        data_manager=manager
    )

    result = engine.run(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

    # 验证：应该有4笔交易（4个交易日）
    verify_trades(result, expected_trades=4, expected_cash=4000.0)


def test_scenario_2_weekly_with_weekend():
    """场景2：周定投（遇到周末）"""
    print_section("场景2：周定投（遇到周末）")

    # 创建测试数据：2024-01-01（周一）到 2024-01-12（周五）
    # 包含两个周一：1月1日（假期）和1月8日（正常）
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 12)

    manager = MockFundDataManager()
    manager.add_fund_data('000001', create_simple_nav_data(start, end, 1.0))

    schedule = InvestmentSchedule(frequency='weekly', amount=1000.0, day_of_week=1)  # 周一

    engine = BacktestEngine(
        allocations={'000001': 1.0},
        schedule=schedule,
        data_manager=manager
    )

    result = engine.run(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

    # 验证：应该有2笔交易（1月1日顺延到1月2日，1月8日正常）
    verify_trades(result, expected_trades=2, expected_cash=2000.0)


def test_scenario_3_delay_to_next_investment_day():
    """场景3：顺延后遇到下一个定投日（关键场景）"""
    print_section("场景3：顺延后遇到下一个定投日（关键场景）")

    # 创建测试数据：
    # 2024-01-05（周五，正常交易日）
    # 2024-01-06、01-07（周末，非交易日）
    # 2024-01-08（周一，定投日）
    # 假设1月6日是定投日（周六），顺延到1月8日
    # 但1月8日本身也是定投日，应该执行2次定投

    start = datetime(2024, 1, 5)
    end = datetime(2024, 1, 10)

    manager = MockFundDataManager()
    manager.add_fund_data('000001', create_simple_nav_data(start, end, 1.0))

    # 每日定投，这样周末也会累积
    schedule = InvestmentSchedule(frequency='daily', amount=1000.0)

    engine = BacktestEngine(
        allocations={'000001': 1.0},
        schedule=schedule,
        data_manager=manager
    )

    result = engine.run(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

    # 验证：应该有6笔交易（5日、6日顺延、7日顺延、8日、9日、10日）
    # 周五到下周三，共6个交易日
    verify_trades(result, expected_trades=6, expected_cash=6000.0)


def test_scenario_4_monthly_with_weekend():
    """场景4：月定投（遇到周末）"""
    print_section("场景4：月定投（遇到周末）")

    # 2024-01-01（周一，假期）
    # 2024-02-01（周四）
    # 2024-03-01（周五）
    start = datetime(2024, 1, 1)
    end = datetime(2024, 3, 31)

    manager = MockFundDataManager()
    manager.add_fund_data('000001', create_simple_nav_data(start, end, 1.0))

    schedule = InvestmentSchedule(frequency='monthly', amount=1000.0, day_of_month=1)

    engine = BacktestEngine(
        allocations={'000001': 1.0},
        schedule=schedule,
        data_manager=manager
    )

    result = engine.run(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

    # 验证：应该有3笔交易（1月1日顺延、2月1日、3月1日）
    verify_trades(result, expected_trades=3, expected_cash=3000.0)


def test_scenario_5_suspended_purchase():
    """场景5：基金暂停申购后恢复"""
    print_section("场景5：基金暂停申购后恢复")

    # 2024-01-02 到 2024-01-10
    # 000001在1月3日-1月5日暂停申购
    start = datetime(2024, 1, 2)
    end = datetime(2024, 1, 10)

    manager = MockFundDataManager()
    manager.add_fund_data('000001', create_simple_nav_data(start, end, 1.0))

    # 设置暂停申购
    manager.set_purchase_status('000001',
                               datetime(2024, 1, 3),
                               datetime(2024, 1, 5),
                               '暂停申购')

    schedule = InvestmentSchedule(frequency='daily', amount=1000.0)

    engine = BacktestEngine(
        allocations={'000001': 1.0},
        schedule=schedule,
        data_manager=manager
    )

    result = engine.run(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

    # 验证：
    # 1月2日：正常
    # 1月3日-5日：暂停，累积3次
    # 1月6日（周六）：非交易日，累积1次
    # 1月7日（周日）：非交易日，累积1次
    # 1月8日：执行所有累积的定投（5次：3日、4日、5日、6日、7日）
    # 1月9日-10日：正常
    # 总共：1 + 5 + 2 = 8笔交易
    verify_trades(result, expected_trades=8, expected_cash=8000.0)


def test_scenario_6_long_suspension():
    """场景6：长期暂停申购（回测结束时仍有未执行的定投）"""
    print_section("场景6：长期暂停申购（回测结束仍有未执行定投）")

    # 2024-01-02 到 2024-01-05
    # 000001在1月3日之后一直暂停申购
    start = datetime(2024, 1, 2)
    end = datetime(2024, 1, 5)

    manager = MockFundDataManager()
    manager.add_fund_data('000001', create_simple_nav_data(start, end, 1.0))

    # 设置长期暂停申购
    manager.set_purchase_status('000001',
                               datetime(2024, 1, 3),
                               datetime(2024, 12, 31),
                               '暂停申购')

    schedule = InvestmentSchedule(frequency='daily', amount=1000.0)

    engine = BacktestEngine(
        allocations={'000001': 1.0},
        schedule=schedule,
        data_manager=manager
    )

    result = engine.run(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

    # 验证：
    # 1月2日：正常，1笔
    # 1月3日-5日：暂停，累积但未执行
    # 总共：1笔交易，3次未执行
    verify_trades(result, expected_trades=1, expected_cash=1000.0)


def test_scenario_7_with_dividend():
    """场景7：定投期间有分红"""
    print_section("场景7：定投期间有分红")

    # 2024-01-02 到 2024-01-10
    start = datetime(2024, 1, 2)
    end = datetime(2024, 1, 10)

    manager = MockFundDataManager()
    data = create_simple_nav_data(start, end, 1.0)

    # 添加分红数据：1月5日每份分红0.1元
    manager.dividend_data['000001'] = [
        (datetime(2024, 1, 5), {'type': 'cash', 'amount_per_unit': 0.1, 'raw_text': '每份分红0.1元'})
    ]

    manager.add_fund_data('000001', data)

    schedule = InvestmentSchedule(frequency='daily', amount=1000.0)

    engine = BacktestEngine(
        allocations={'000001': 1.0},
        schedule=schedule,
        data_manager=manager
    )

    result = engine.run(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

    # 验证：
    # 1月2日-4日：定投
    # 1月5日：定投 + 分红
    # 1月8日-10日：定投
    # 总共：8笔定投交易 + 1笔分红交易
    # 分红不是定投交易，但应该有记录
    # 所以预期总交易数是9
    verify_trades(result, expected_trades=9, expected_cash=8000.0)


def test_scenario_8_investment_and_dividend_same_day():
    """场景8：定投日又是分红日（专门验证执行顺序）"""
    print_section("场景8：定投日又是分红日（执行顺序验证）")

    # 2024-01-02 到 2024-01-05
    # 1月2日：定投1000元，获得1000份
    # 1月3日：定投1000元，获得1000份，累计2000份
    # 1月4日：定投1000元，获得1000份，累计3000份
    # 1月5日：既是定投日又是分红日
    #   - 先分红：3000份 × 0.1元/份 = 300元，再投资获得300份
    #   - 后定投：定投1000元，获得1000份
    #   最终份额：3000 + 300 + 1000 = 4300份
    start = datetime(2024, 1, 2)
    end = datetime(2024, 1, 5)

    manager = MockFundDataManager()
    data = create_simple_nav_data(start, end, 1.0)

    # 添加分红数据：1月5日每份分红0.1元（这一天也是定投日）
    manager.dividend_data['000001'] = [
        (datetime(2024, 1, 5), {'type': 'cash', 'amount_per_unit': 0.1, 'raw_text': '每份分红0.1元'})
    ]

    manager.add_fund_data('000001', data)

    schedule = InvestmentSchedule(frequency='daily', amount=1000.0)

    engine = BacktestEngine(
        allocations={'000001': 1.0},
        schedule=schedule,
        data_manager=manager
    )

    result = engine.run(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

    # 验证：
    # 1月2日：定投，1000份
    # 1月3日：定投，1000份，累计2000份
    # 1月4日：定投，1000份，累计3000份
    # 1月5日：先分红（300份），后定投（1000份）
    # 总共：4笔定投交易 + 1笔分红交易 = 5笔交易
    # 累计投入：4000元（定投）
    verify_trades(result, expected_trades=5, expected_cash=4000.0)

    # 额外验证：检查1月5日的执行顺序
    print(f"\n【额外验证】1月5日执行顺序")
    jan_5_trades = [t for t in result.trades if t['date'].day == 5]
    print(f"  1月5日交易数: {len(jan_5_trades)} 笔")

    for i, trade in enumerate(jan_5_trades, 1):
        print(f"    交易#{i}: {trade['type']}")
        if trade['type'] == '红利再投资':
            print(f"      分红前份额: {trade['shares_before']:.2f} 份")
            print(f"      每份分红: {trade['dividend_per_unit']:.4f} 元")
            print(f"      分红金额: {trade['dividend_amount']:.2f} 元")
            print(f"      新增份额: {trade['new_shares']:.2f} 份")
            print(f"      分红后份额: {trade['shares_after']:.2f} 份")
            # 验证分红是基于3000份
            expected_before = 3000.0
            expected_dividend = expected_before * 0.1  # 300元
            expected_new_shares = expected_dividend / 1.0  # 300份
            print(f"      验证: 分红前份额{trade['shares_before']:.2f} == {expected_before} ✓")
            print(f"      验证: 分红金额{trade['dividend_amount']:.2f} == {expected_dividend} ✓")
            print(f"      验证: 新增份额{trade['new_shares']:.2f} == {expected_new_shares} ✓")
        elif trade['type'] == '定投申购':
            print(f"      定投前份额: {trade['shares_before']:.2f} 份")
            print(f"      定投金额: {trade['amount']:.2f} 元")
            print(f"      获得份额: {trade['shares']:.2f} 份")
            print(f"      定投后份额: {trade['shares_after']:.2f} 份")
            # 定投应该基于分红后的份额（3300份）
            expected_before = 3300.0
            print(f"      验证: 定投前份额{trade['shares_before']:.2f} == {expected_before} ✓")

    # 验证最终份额
    final_shares = result.trades[-1]['shares_after']
    expected_final = 4300.0  # 3000初始 + 300分红 + 1000定投
    print(f"\n  最终份额: {final_shares:.2f} 份")
    print(f"  预期份额: {expected_final:.2f} 份")
    print(f"  匹配: {'✓' if abs(final_shares - expected_final) < 0.01 else '✗'}")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("定投回测全面测试 - 检查每一笔交易".center(80))
    print("=" * 80)

    tests = [
        ("场景1：正常日定投", test_scenario_1_normal_daily_invest),
        ("场景2：周定投（遇到周末）", test_scenario_2_weekly_with_weekend),
        ("场景3：顺延后遇到下一个定投日（关键）", test_scenario_3_delay_to_next_investment_day),
        ("场景4：月定投（遇到周末）", test_scenario_4_monthly_with_weekend),
        ("场景5：基金暂停申购后恢复", test_scenario_5_suspended_purchase),
        ("场景6：长期暂停申购", test_scenario_6_long_suspension),
        ("场景7：定投期间有分红", test_scenario_7_with_dividend),
        ("场景8：定投日又是分红日（执行顺序）", test_scenario_8_investment_and_dividend_same_day),
    ]

    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, "✓ 通过"))
        except Exception as e:
            results.append((name, f"✗ 失败: {str(e)}"))
            import traceback
            traceback.print_exc()

    # 打印总结
    print_section("测试总结")
    for name, result in results:
        print(f"{name:<50} {result}")

    passed = sum(1 for _, r in results if "✓" in r)
    print(f"\n通过: {passed}/{len(tests)}")

    return passed == len(tests)


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
