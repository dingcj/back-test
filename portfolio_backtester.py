#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投资组合回测引擎

功能：
- 定投回测（日定投、周定投、月定投）
- 红利再投资
- T+1净值逻辑（避免未来函数）
- 详细的交易日志
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from fund_data_manager import FundDataManager, parse_portfolio_input


class InvestmentSchedule:
    """投资计划配置"""

    def __init__(self, frequency: str, amount: float,
                 day_of_week: Optional[int] = None,
                 day_of_month: Optional[int] = None):
        """
        初始化投资计划

        Args:
            frequency: 投资频率 ('daily', 'weekly', 'monthly')
            amount: 每次投资金额
            day_of_week: 周定投时指定星期几 (1-7, 1=周一)
            day_of_month: 月定投时指定每月几号 (1-31)
        """
        self.frequency = frequency
        self.amount = amount
        self.day_of_week = day_of_week
        self.day_of_month = day_of_month

    def is_investment_day(self, date: datetime) -> bool:
        """
        判断是否为投资日

        Args:
            date: 日期

        Returns:
            是否为投资日
        """
        if self.frequency == 'daily':
            return True

        elif self.frequency == 'weekly':
            if self.day_of_week is None:
                raise ValueError("周定投需要指定 day_of_week")
            # 星期几 (1-7, 1=周一)
            return date.isoweekday() == self.day_of_week

        elif self.frequency == 'monthly':
            if self.day_of_month is None:
                raise ValueError("月定投需要指定 day_of_month")
            return date.day == self.day_of_month

        return False


class Portfolio:
    """投资组合管理"""

    def __init__(self, initial_cash: float, target_allocations: Dict[str, float]):
        """
        初始化投资组合

        Args:
            initial_cash: 初始现金
            target_allocations: 目标配置比例 {fund_code: proportion}
        """
        self.cash = initial_cash
        self.holdings = {}  # {fund_code: shares}
        self.target_allocations = target_allocations
        self.trades = []  # 交易记录

    def get_value(self, fund_navs: Dict[str, float]) -> float:
        """
        计算组合总价值（持仓市值）

        Args:
            fund_navs: {fund_code: nav} 字典

        Returns:
            持仓总价值
        """
        total = 0
        for fund_code, shares in self.holdings.items():
            if fund_code in fund_navs:
                total += shares * fund_navs[fund_code]
        return total

    def invest(self, investment_amount: float, fund_navs: Dict[str, float],
               date: datetime, prev_navs: Dict[str, float], prev_date: datetime):
        """
        定投日执行投资

        Args:
            investment_amount: 定投金额
            fund_navs: 当日净值（T日）
            date: 定投日
            prev_navs: 前一日净值（T-1日）
            prev_date: 前一日日期
        """
        print(f"\n{'='*60}")
        print(f"定投日: {date.strftime('%Y-%m-%d')}")
        print(f"定投金额: {investment_amount:.2f} 元")
        print(f"{'='*60}")

        # 记录定投前的份额
        shares_before = {code: self.holdings.get(code, 0) for code in self.target_allocations.keys()}

        # 第一步：显示当前持仓估值（使用T-1日净值）
        print(f"\n【当前持仓估值】(使用 {prev_date.strftime('%Y-%m-%d')} 净值)")
        total_holding_value = 0
        for fund_code in self.target_allocations.keys():
            shares = shares_before[fund_code]
            prev_nav = prev_navs.get(fund_code, 0)
            value = shares * prev_nav
            total_holding_value += value
            print(f"  {fund_code}: {shares:.2f} 份 × {prev_nav:.4f} 元/份 = {value:.2f} 元")

        print(f"\n  持仓总市值: {total_holding_value:.2f} 元")
        print(f"  累计投入: {abs(self.cash):.2f} 元")
        print(f"  总资产: {total_holding_value:.2f} 元")

        # 第二步：执行定投申购（使用T日净值）
        print(f"\n【定投申购】(使用 {date.strftime('%Y-%m-%d')} 净值)")

        for fund_code, target_ratio in self.target_allocations.items():
            # 按目标比例分配本次定投金额
            invest_amount = investment_amount * target_ratio
            nav = fund_navs[fund_code]

            # 执行申购（使用当日净值T）
            shares = invest_amount / nav
            self.holdings[fund_code] = self.holdings.get(fund_code, 0) + shares
            self.cash -= invest_amount

            # 详细日志输出
            print(f"\n  基金: {fund_code}")
            print(f"    目标比例: {target_ratio*100:.1f}%")
            print(f"    定投前份额: {shares_before[fund_code]:.2f} 份")
            print(f"    投资金额: {invest_amount:.2f} 元")
            print(f"    定投日净值: {nav:.4f} 元/份 (日期: {date.strftime('%Y-%m-%d')})")
            print(f"    计算过程: {invest_amount:.2f} ÷ {nav:.4f} = {shares:.2f} 份")
            print(f"    获得份额: {shares:.2f} 份")
            print(f"    定投后份额: {self.holdings[fund_code]:.2f} 份")

            # 记录交易
            self.trades.append({
                'date': date,
                'fund_code': fund_code,
                'type': '定投申购',
                'shares_before': shares_before[fund_code],
                'shares': shares,
                'shares_after': self.holdings[fund_code],
                'holding_value_before': shares_before[fund_code] * prev_navs.get(fund_code, 0),
                'nav': nav,
                'nav_date': date,
                'prev_nav': prev_navs.get(fund_code, 0),
                'prev_nav_date': prev_date,
                'amount': invest_amount,
                'calculation': f"{invest_amount:.2f}÷{nav:.4f}={shares:.2f}份"
            })

        # 输出定投后所有基金份额汇总
        print(f"\n{'─'*60}")
        print(f"定投后份额汇总:")
        for fund_code in self.target_allocations.keys():
            print(f"  {fund_code}: {self.holdings[fund_code]:.2f} 份")
        print(f"累计投入: {abs(self.cash):.2f} 元")
        print(f"{'='*60}")

    def process_dividends(self, date: datetime, fund_navs: Dict[str, float],
                         dividend_info: Dict[str, Dict]):
        """
        处理红利再投资

        Args:
            date: 分红日
            fund_navs: 当日净值（T日）
            dividend_info: {fund_code: dividend_dict} 字典
        """
        has_dividend = False

        for fund_code, shares_before in list(self.holdings.items()):
            if fund_code not in dividend_info or dividend_info[fund_code] is None:
                continue

            info = dividend_info[fund_code]
            if info['type'] != 'cash':
                continue

            if not has_dividend:
                print(f"\n{'='*60}")
                print(f"分红日: {date.strftime('%Y-%m-%d')}")
                print(f"{'='*60}")
                has_dividend = True

            dividend_per_unit = info['amount_per_unit']
            dividend_amount = shares_before * dividend_per_unit
            nav = fund_navs[fund_code]
            new_shares = dividend_amount / nav

            self.holdings[fund_code] = shares_before + new_shares

            # 详细日志输出
            print(f"\n基金: {fund_code}")
            print(f"  分红信息: {info['raw_text']}")
            print(f"  每份分红: {dividend_per_unit:.4f} 元")
            print(f"  分红前份额: {shares_before:.2f} 份")
            print(f"  分红金额: {shares_before:.2f} × {dividend_per_unit:.4f} = {dividend_amount:.2f} 元")
            print(f"  使用净值日期: {date.strftime('%Y-%m-%d')} (T日)")
            print(f"  再投资净值: {nav:.4f} 元/份")
            print(f"  新增份额: {dividend_amount:.2f} ÷ {nav:.4f} = {new_shares:.2f} 份")
            print(f"  分红后份额: {self.holdings[fund_code]:.2f} 份")

            # 记录交易
            self.trades.append({
                'date': date,
                'fund_code': fund_code,
                'type': '红利再投资',
                'shares_before': shares_before,
                'dividend_per_unit': dividend_per_unit,
                'dividend_amount': dividend_amount,
                'nav': nav,
                'nav_date': date,
                'new_shares': new_shares,
                'shares_after': self.holdings[fund_code],
                'calculation': f"{shares_before:.2f}×{dividend_per_unit:.4f}={dividend_amount:.2f}元→{new_shares:.2f}份"
            })


class BacktestEngine:
    """回测执行引擎"""

    def __init__(self, allocations: Dict[str, float], schedule: InvestmentSchedule,
                 data_manager: FundDataManager):
        """
        初始化回测引擎

        Args:
            allocations: 投资组合配置 {fund_code: proportion}
            schedule: 投资计划
            data_manager: 数据管理器
        """
        self.allocations = allocations
        self.schedule = schedule
        self.data_manager = data_manager
        self.fund_codes = list(allocations.keys())

    def run(self, start_date: str, end_date: str) -> 'BacktestResult':
        """
        执行回测

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            回测结果
        """
        print(f"\n{'='*60}")
        print(f"开始回测")
        print(f"回测期间: {start_date} 至 {end_date}")
        print(f"投资频率: {self.schedule.frequency}")
        print(f"定投金额: {self.schedule.amount:.2f} 元")
        print(f"{'='*60}\n")

        # 加载所有基金数据
        print("加载基金数据...")
        fund_data = self.data_manager.get_multi_fund_data(self.fund_codes)
        print(f"已加载 {len(fund_data)} 只基金的数据\n")

        # 获取共同交易日
        trading_days = self.data_manager.get_common_trading_days(fund_data)
        print(f"共同交易日: {len(trading_days)} 天\n")

        # 过滤回测期间
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        trading_days = [d for d in trading_days if start_dt <= d <= end_dt]

        if not trading_days:
            raise ValueError(f"在回测期间 {start_date} 至 {end_date} 没有交易日")

        print(f"回测期间交易日: {len(trading_days)} 天\n")

        # 初始化组合
        portfolio = Portfolio(0, self.allocations)

        # 逐日执行
        portfolio_history = []
        prev_date = None
        prev_navs = {}

        for i, current_date in enumerate(trading_days):
            # 获取当日净值
            current_navs = {}
            for code in self.fund_codes:
                nav = self.data_manager.get_nav_for_date(code, current_date, fund_data)
                if nav is None:
                    print(f"警告: {current_date.strftime('%Y-%m-%d')} 基金 {code} 没有净值数据，跳过")
                    continue
                current_navs[code] = nav

            # 确保所有基金都有数据
            if len(current_navs) != len(self.fund_codes):
                continue

            # 第一步：先处理分红（使用T日净值）
            dividend_info = {}
            for code in self.fund_codes:
                div = self.data_manager.get_dividend_for_date(code, current_date, fund_data)
                dividend_info[code] = div

            if any(dividend_info.values()):
                portfolio.process_dividends(current_date, current_navs, dividend_info)

            # 第二步：如果是定投日，检查申购状态后执行定投（使用T日净值）
            if self.schedule.is_investment_day(current_date):
                # 检查所有基金是否都可以申购
                can_purchase, blocked_funds = self.data_manager.can_purchase_all(
                    self.fund_codes, current_date, fund_data
                )

                if not can_purchase:
                    # 有基金暂停申购，跳过本次定投
                    print(f"\n【定投跳过】{current_date.strftime('%Y-%m-%d')}")
                    print(f"  原因: 以下基金暂停申购/封闭: {', '.join(blocked_funds)}")
                    print(f"  说明: 将等待下一个所有基金都可申购的交易日")
                    continue

                if prev_date is None:
                    # 第一次定投，没有前一日数据
                    prev_date = current_date
                    prev_navs = current_navs.copy()

                portfolio.invest(
                    investment_amount=self.schedule.amount,
                    fund_navs=current_navs,
                    date=current_date,
                    prev_navs=prev_navs,
                    prev_date=prev_date
                )

            # 记录当日组合价值（使用T日净值）
            total_value = portfolio.get_value(current_navs)

            portfolio_history.append({
                'date': current_date,
                'total_value': total_value,
                'cash': abs(portfolio.cash),  # 累计投入（取绝对值）
                'holdings_value': total_value,  # 持仓市值 = 总价值
                'holdings': portfolio.holdings.copy()
            })

            # 更新前一日数据
            prev_date = current_date
            prev_navs = current_navs.copy()

        print(f"\n{'='*60}")
        print(f"回测完成")
        print(f"{'='*60}\n")

        # 生成结果
        return BacktestResult(portfolio_history, portfolio.trades, self.allocations, self.schedule)


class BacktestResult:
    """回测结果"""

    def __init__(self, portfolio_history: List[Dict], trades: List[Dict],
                 allocations: Dict[str, float], schedule: InvestmentSchedule):
        """
        初始化回测结果

        Args:
            portfolio_history: 组合历史记录
            trades: 交易记录
            allocations: 投资组合配置
            schedule: 投资计划
        """
        self.history = portfolio_history
        self.trades = trades
        self.allocations = allocations
        self.schedule = schedule

    def calculate_metrics(self) -> Dict:
        """计算绩效指标"""
        if not self.history:
            return {}

        # 提取数据
        values = [h['total_value'] for h in self.history]
        investments = [t['amount'] for t in self.trades if t['type'] == '定投申购']

        total_invested = sum(investments) if investments else 0
        final_value = values[-1] if values else 0
        total_return = (final_value - total_invested) / total_invested if total_invested > 0 else 0

        # 最大回撤
        running_max = pd.Series(values).cummax()
        drawdown = (pd.Series(values) - running_max) / running_max
        max_drawdown = drawdown.min()

        # 年化收益率
        if len(self.history) > 1:
            days = (self.history[-1]['date'] - self.history[0]['date']).days
            if days > 0:
                annualized_return = (final_value / total_invested) ** (365 / days) - 1 if total_invested > 0 else 0
            else:
                annualized_return = 0
        else:
            annualized_return = 0

        return {
            'total_invested': total_invested,
            'final_value': final_value,
            'total_return': total_return * 100,  # 百分比
            'annualized_return': annualized_return * 100,  # 百分比
            'max_drawdown': max_drawdown * 100,  # 百分比
            'num_trades': len(self.trades),
            'investment_days': len(self.history)
        }

    def generate_report(self) -> str:
        """生成文本报告"""
        metrics = self.calculate_metrics()

        report = []
        report.append("=" * 60)
        report.append("投资组合回测报告")
        report.append("=" * 60)
        report.append("")

        # 投资组合配置
        report.append("投资组合配置:")
        for code, ratio in self.allocations.items():
            report.append(f"  {code}: {ratio*100:.1f}%")
        report.append("")

        # 投资计划
        report.append("投资计划:")
        report.append(f"  频率: {self.schedule.frequency}")
        report.append(f"  金额: {self.schedule.amount:.2f} 元")
        if self.schedule.day_of_week:
            report.append(f"  投资日: 每周星期{self.schedule.day_of_week}")
        if self.schedule.day_of_month:
            report.append(f"  投资日: 每月{self.schedule.day_of_month}日")
        report.append("")

        # 绩效指标
        report.append("绩效指标:")
        report.append(f"  总投入: {metrics['total_invested']:,.2f} 元")
        report.append(f"  最终资产: {metrics['final_value']:,.2f} 元")
        report.append(f"  总收益率: {metrics['total_return']:.2f}%")
        report.append(f"  年化收益率: {metrics['annualized_return']:.2f}%")
        report.append(f"  最大回撤: {metrics['max_drawdown']:.2f}%")
        report.append(f"  交易次数: {metrics['num_trades']} 次")
        report.append("")

        report.append("=" * 60)

        return "\n".join(report)

    def save_trades(self, filepath: str):
        """保存交易记录到CSV"""
        if not self.trades:
            print("没有交易记录")
            return

        df = pd.DataFrame(self.trades)

        # 重命名列
        column_mapping = {
            'date': '交易日期',
            'fund_code': '基金代码',
            'type': '交易类型',
            'shares_before': '定投前份额',
            'shares': '获得份额',
            'shares_after': '定投后份额',
            'holding_value_before': '持仓市值(估)',
            'nav': '定投净值',
            'prev_nav': '估值净值',
            'nav_date': '定投日',
            'prev_nav_date': '估值日',
            'amount': '金额',
            'calculation': '计算过程',
            'dividend_per_unit': '每份分红',
            'dividend_amount': '分红金额',
            'new_shares': '新增份额'
        }

        df = df.rename(columns=column_mapping)

        # 选择需要的列（按顺序）
        columns_order = ['交易日期', '基金代码', '交易类型', '定投前份额', '持仓市值(估)',
                        '获得份额', '定投后份额', '定投净值', '估值净值', '定投日', '估值日',
                        '金额', '每份分红', '分红金额', '计算过程']

        # 只保留存在的列
        columns_order = [col for col in columns_order if col in df.columns]

        df = df[columns_order]

        # 格式化日期
        if '交易日期' in df.columns:
            df['交易日期'] = df['交易日期'].dt.strftime('%Y-%m-%d')
        if '定投日' in df.columns:
            df['定投日'] = df['定投日'].dt.strftime('%Y-%m-%d')
        if '估值日' in df.columns:
            df['估值日'] = df['估值日'].dt.strftime('%Y-%m-%d')

        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"交易记录已保存到: {filepath}")

    def save_portfolio_values(self, filepath: str):
        """保存组合价值历史到CSV"""
        if not self.history:
            print("没有组合历史记录")
            return

        # 构建数据
        data = []
        fund_codes = list(self.allocations.keys())

        for h in self.history:
            row = {
                '日期': h['date'].strftime('%Y-%m-%d'),
                '总资产': h['total_value'],
                '现金': h['cash'],
                '持仓市值': h['holdings_value']
            }

            # 添加各基金份额
            for code in fund_codes:
                row[f'{code}份额'] = h['holdings'].get(code, 0)

            # 添加当日投资金额
            daily_investment = sum([
                t['amount'] for t in self.trades
                if t['date'] == h['date'] and t['type'] == '定投申购'
            ])
            row['当日投资'] = daily_investment

            data.append(row)

        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"组合价值历史已保存到: {filepath}")
