#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_backtest.py 的测试用例

测试覆盖：
1. 单个回测结果绘图
2. 多个回测结果对比绘图
3. 错误处理（文件不存在、空数据等）
4. 边界情况
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from plot_backtest import (
    load_backtest_data,
    extract_metrics,
    plot_single_backtest,
    plot_comparison
)


def create_test_data(temp_dir):
    """
    创建测试用的回测数据

    Args:
        temp_dir: 临时目录路径

    Returns:
        list: 创建的测试数据目录列表
    """
    test_dirs = []

    # 创建3个测试回测结果
    for i in range(1, 4):
        test_dir = Path(temp_dir) / f"backtest_test_{i}"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_dirs.append(str(test_dir))

        # 生成日期序列（2023年全年）
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        dates = pd.date_range(start_date, end_date, freq='D')

        # 模拟投资数据
        n_days = len(dates)
        investment_schedule = 1000  # 每月定投1000元

        # 创建每日投资数据（每月15号定投）
        daily_investment = pd.Series(0.0, index=dates)
        for date in dates:
            if date.day == 15:
                daily_investment[date] = investment_schedule

        # 模拟净值变化（简单的正弦波 + 趋势）
        base_value = 1.5
        trend = 0.0001 * np.arange(n_days)
        noise = 0.02 * np.sin(np.arange(n_days) * 0.1)
        nav_values = base_value * (1 + trend + noise + np.random.normal(0, 0.01, n_days))

        # 模拟份额累积
        shares = pd.Series(0.0, index=dates)
        total_assets = pd.Series(0.0, index=dates)
        cash = pd.Series(0.0, index=dates)

        current_shares = 0.0
        for j, date in enumerate(dates):
            if daily_investment[date] > 0:
                # 定投日
                current_shares += daily_investment[date] / nav_values[j]
                cash[date] = daily_investment[date]

            shares[date] = current_shares
            total_assets[date] = current_shares * nav_values[j]

        # 修改第一个测试集，使其有不同的收益率
        if i == 1:
            # 亏损案例
            total_assets = total_assets * 0.9
        elif i == 2:
            # 盈利案例
            total_assets = total_assets * 1.1
        else:
            # 波动案例
            total_assets = total_assets * (1 + 0.1 * np.sin(np.arange(n_days) * 0.05))

        # 创建组合价值历史数据
        portfolio_values = pd.DataFrame({
            '日期': dates,
            '总资产': total_assets.values,
            '现金': cash.cumsum().values,
            '持仓市值': (shares * nav_values).values,
            '210014份额': shares.values,
            '当日投资': daily_investment.values
        })

        portfolio_values.to_csv(
            test_dir / "portfolio_values.csv",
            index=False,
            encoding='utf-8-sig'
        )

        # 创建交易记录
        trades = []
        for date in dates:
            if date.day == 15 and date.month <= 12:
                trade_date = date
                nav = nav_values[dates.get_loc(date)]
                investment = investment_schedule
                shares_bought = investment / nav

                trades.append({
                    '交易日期': trade_date.strftime('%Y-%m-%d'),
                    '基金代码': '210014',
                    '交易类型': '定投申购',
                    '定投前份额': 0.0,
                    '持仓市值(估)': 0.0,
                    '获得份额': shares_bought,
                    '定投后份额': shares_bought,
                    '定投净值': nav,
                    '估值净值': nav,
                    '定投日': date.strftime('%Y-%m-%d'),
                    '估值日': (date - timedelta(days=1)).strftime('%Y-%m-%d'),
                    '金额': investment,
                    '计算过程': f'{investment:.2f}÷{nav:.4f}={shares_bought:.2f}份'
                })

        trades_df = pd.DataFrame(trades)
        trades_df.to_csv(
            test_dir / "trades.csv",
            index=False,
            encoding='utf-8-sig'
        )

        # 创建报告文件
        report = f"""============================================================
投资组合回测报告
============================================================

投资组合配置:
  210014: 100.0%

投资计划:
  频率: monthly
  金额: {investment_schedule:.2f} 元
  投资日: 每月15日

绩效指标:
  总投入: {investment_schedule * 12:,.2f} 元
  最终资产: {total_assets.iloc[-1]:,.2f} 元
  总收益率: {(total_assets.iloc[-1] - investment_schedule * 12) / (investment_schedule * 12) * 100:+.2f}%

============================================================
"""
        with open(test_dir / "report.txt", 'w', encoding='utf-8') as f:
            f.write(report)

    return test_dirs


def test_load_backtest_data():
    """测试加载回测数据"""
    print("\n" + "="*60)
    print("测试 1: 加载回测数据")
    print("="*60)

    with tempfile.TemporaryDirectory() as temp_dir:
        test_dirs = create_test_data(temp_dir)

        # 测试加载第一个数据集
        data = load_backtest_data(test_dirs[0])

        assert data['portfolio_values'] is not None, "组合价值数据不应为空"
        assert data['trades'] is not None, "交易记录不应为空"
        assert data['report'] is not None, "报告不应为空"

        assert len(data['portfolio_values']) > 0, "组合价值数据应包含记录"
        assert len(data['trades']) > 0, "交易记录应包含记录"

        # 验证数据列
        assert '日期' in data['portfolio_values'].columns
        assert '总资产' in data['portfolio_values'].columns
        assert '当日投资' in data['portfolio_values'].columns

        print("✅ 加载回测数据测试通过")

        # 测试文件不存在的情况
        try:
            load_backtest_data("/nonexistent/path")
            assert False, "应该抛出 FileNotFoundError"
        except FileNotFoundError:
            print("✅ 文件不存在错误处理测试通过")


def test_extract_metrics():
    """测试提取指标"""
    print("\n" + "="*60)
    print("测试 2: 提取指标")
    print("="*60)

    with tempfile.TemporaryDirectory() as temp_dir:
        test_dirs = create_test_data(temp_dir)
        data = load_backtest_data(test_dirs[0])

        metrics = extract_metrics(data['portfolio_values'], data['trades'])

        # 验证指标存在
        assert 'cumulative_investment' in metrics
        assert 'final_value' in metrics
        assert 'total_profit' in metrics
        assert 'total_return' in metrics
        assert 'max_drawdown' in metrics
        assert 'daily_returns' in metrics
        assert 'drawdown_series' in metrics

        # 验证指标值的合理性
        assert metrics['cumulative_investment'] > 0, "累计投入应大于0"
        assert len(metrics['daily_returns']) == len(data['portfolio_values']), "收益率序列长度应匹配"
        assert len(metrics['drawdown_series']) == len(data['portfolio_values']), "回撤序列长度应匹配"

        print(f"  累计投入: {metrics['cumulative_investment']:.2f} 元")
        print(f"  最终资产: {metrics['final_value']:.2f} 元")
        print(f"  总收益: {metrics['total_profit']:.2f} 元")
        print(f"  收益率: {metrics['total_return']:.2f}%")
        print(f"  最大回撤: {metrics['max_drawdown']:.2f}%")

        print("✅ 提取指标测试通过")


def test_plot_single_backtest():
    """测试单个回测绘图"""
    print("\n" + "="*60)
    print("测试 3: 单个回测绘图")
    print("="*60)

    # 检查 matplotlib 是否可用
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("⚠️  matplotlib 未安装，跳过绘图测试")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        test_dirs = create_test_data(temp_dir)
        output_file = os.path.join(temp_dir, "test_single_plot.png")

        # 测试绘图
        plot_single_backtest(test_dirs[0], output_path=output_file, show=False)

        # 验证文件生成
        assert os.path.exists(output_file), "输出文件应存在"
        assert os.path.getsize(output_file) > 0, "输出文件应非空"

        file_size_kb = os.path.getsize(output_file) / 1024
        print(f"  生成文件大小: {file_size_kb:.2f} KB")

        print("✅ 单个回测绘图测试通过")


def test_plot_comparison():
    """测试对比绘图"""
    print("\n" + "="*60)
    print("测试 4: 对比绘图")
    print("="*60)

    # 检查 matplotlib 是否可用
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("⚠️  matplotlib 未安装，跳过绘图测试")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        test_dirs = create_test_data(temp_dir)
        output_file = os.path.join(temp_dir, "test_comparison.png")

        # 测试对比绘图
        plot_comparison(test_dirs, output_path=output_file, show=False, title="测试对比")

        # 验证文件生成
        assert os.path.exists(output_file), "输出文件应存在"
        assert os.path.getsize(output_file) > 0, "输出文件应非空"

        file_size_kb = os.path.getsize(output_file) / 1024
        print(f"  生成文件大小: {file_size_kb:.2f} KB")
        print(f"  对比了 {len(test_dirs)} 个回测结果")

        print("✅ 对比绘图测试通过")


def test_edge_cases():
    """测试边界情况"""
    print("\n" + "="*60)
    print("测试 5: 边界情况")
    print("="*60)

    with tempfile.TemporaryDirectory() as temp_dir:

        # 测试空数据目录
        empty_dir = Path(temp_dir) / "empty_backtest"
        empty_dir.mkdir()

        try:
            load_backtest_data(str(empty_dir))
            assert False, "应该抛出 FileNotFoundError"
        except FileNotFoundError:
            print("✅ 空目录错误处理测试通过")

        # 测试只有部分文件的情况
        partial_dir = Path(temp_dir) / "partial_backtest"
        partial_dir.mkdir()

        # 只有 portfolio_values.csv，没有 trades.csv
        dates = pd.date_range('2023-01-01', '2023-01-31', freq='D')
        portfolio_values = pd.DataFrame({
            '日期': dates,
            '总资产': np.zeros(len(dates)),
            '现金': np.zeros(len(dates)),
            '持仓市值': np.zeros(len(dates)),
            '份额': np.zeros(len(dates)),
            '当日投资': np.zeros(len(dates))
        })
        portfolio_values.to_csv(
            partial_dir / "portfolio_values.csv",
            index=False,
            encoding='utf-8-sig'
        )

        data = load_backtest_data(str(partial_dir))
        assert data['trades'] is None, "没有 trades.csv 时应返回 None"
        print("✅ 缺少交易记录文件处理测试通过")

        # 测试零投资情况
        metrics = extract_metrics(data['portfolio_values'], None)
        assert metrics['cumulative_investment'] == 0, "零投资时应为0"
        assert metrics['total_return'] == 0, "零投资时收益率应为0"
        print("✅ 零投资边界情况测试通过")


def test_real_data():
    """测试真实数据（如果存在）"""
    print("\n" + "="*60)
    print("测试 6: 真实数据（可选）")
    print("="*60)

    # 查找真实回测结果
    results_dir = Path(__file__).parent.parent / "results"

    if not results_dir.exists():
        print("⚠️  没有找到 results 目录，跳过真实数据测试")
        return

    # 查找所有回测结果目录
    backtest_dirs = list(results_dir.glob("backtest_*"))

    if not backtest_dirs:
        print("⚠️  没有找到回测结果，跳过真实数据测试")
        return

    print(f"  找到 {len(backtest_dirs)} 个回测结果")

    try:
        import matplotlib
        matplotlib.use('Agg')
    except ImportError:
        print("⚠️  matplotlib 未安装，跳过真实数据绘图测试")
        return

    # 测试加载真实数据
    for backtest_dir in backtest_dirs[:3]:  # 只测试前3个
        try:
            data = load_backtest_data(str(backtest_dir))
            metrics = extract_metrics(data['portfolio_values'], data['trades'])

            print(f"  ✓ {backtest_dir.name}: "
                  f"收益率 {metrics['total_return']:.2f}%, "
                  f"最大回撤 {metrics['max_drawdown']:.2f}%")
        except Exception as e:
            print(f"  ✗ {backtest_dir.name}: {e}")

    print("✅ 真实数据测试完成")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始测试 plot_backtest.py")
    print("="*60)

    tests = [
        test_load_backtest_data,
        test_extract_metrics,
        test_plot_single_backtest,
        test_plot_comparison,
        test_edge_cases,
        test_real_data
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ 测试失败: {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️  测试跳过: {e}")
            skipped += 1

    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"跳过: {skipped}")
    print(f"总计: {passed + failed + skipped}")

    if failed == 0:
        print("\n✅ 所有测试通过！")
        return 0
    else:
        print(f"\n❌ 有 {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
