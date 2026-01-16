#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测结果可视化工具

用于读取回测结果数据并生成图表

示例用法:
    # 绘制单个回测结果
    python plot_backtest.py -d results/backtest_20260116_012811_210014100

    # 绘制多个回测结果进行对比
    python plot_backtest.py -d results/backtest_* -o comparison.png

    # 指定自定义图表标题
    python plot_backtest.py -d results/backtest_* -t "定投策略对比"
"""

import argparse
import glob
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np


def load_backtest_data(data_dir):
    """
    加载回测数据

    Args:
        data_dir: 回测结果目录路径

    Returns:
        dict: 包含 portfolio_values, trades, report 的字典
    """
    data_dir = Path(data_dir)

    # 读取组合价值历史
    values_file = data_dir / "portfolio_values.csv"
    if not values_file.exists():
        raise FileNotFoundError(f"找不到组合价值文件: {values_file}")

    # 处理 UTF-8 BOM
    portfolio_values = pd.read_csv(values_file, encoding='utf-8-sig')
    portfolio_values['日期'] = pd.to_datetime(portfolio_values['日期'])

    # 读取交易记录
    trades_file = data_dir / "trades.csv"
    trades = None
    if trades_file.exists():
        trades = pd.read_csv(trades_file, encoding='utf-8-sig')
        trades['交易日期'] = pd.to_datetime(trades['交易日期'])

    # 读取报告
    report_file = data_dir / "report.txt"
    report = None
    if report_file.exists():
        with open(report_file, 'r', encoding='utf-8') as f:
            report = f.read()

    return {
        'portfolio_values': portfolio_values,
        'trades': trades,
        'report': report
    }


def extract_metrics(portfolio_values, trades):
    """
    从数据中提取关键指标

    Args:
        portfolio_values: 组合价值数据
        trades: 交易记录数据

    Returns:
        dict: 关键指标字典
    """
    # 计算累计投入（从交易记录中获取）
    if trades is not None and len(trades) > 0:
        cumulative_investment = trades['金额'].sum()
    else:
        # 从每日数据中计算
        cumulative_investment = portfolio_values['当日投资'].sum()

    # 最终资产
    final_value = portfolio_values['总资产'].iloc[-1]

    # 总收益
    total_profit = final_value - cumulative_investment

    # 收益率
    if cumulative_investment > 0:
        total_return = (total_profit / cumulative_investment) * 100
    else:
        total_return = 0

    # 计算每日收益率（使用每日累计投入）
    df = portfolio_values.copy()
    df['累计投入'] = df['当日投资'].cumsum()  # 计算每日累计投入
    # 避免除以0
    df['收益率'] = np.where(
        df['累计投入'] > 0,
        (df['总资产'] - df['累计投入']) / df['累计投入'] * 100,
        0
    )

    # 最大回撤
    cummax = df['总资产'].cummax()
    drawdown = (df['总资产'] - cummax) / cummax * 100
    max_drawdown = drawdown.min()

    return {
        'cumulative_investment': cumulative_investment,
        'final_value': final_value,
        'total_profit': total_profit,
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'daily_returns': df['收益率'].values,
        'drawdown_series': drawdown.values
    }


def plot_single_backtest(data_dir, output_path=None, show=False):
    """
    绘制单个回测结果的图表

    Args:
        data_dir: 回测结果目录
        output_path: 输出文件路径
        show: 是否显示图表
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # 加载数据
    data = load_backtest_data(data_dir)
    portfolio_values = data['portfolio_values']
    metrics = extract_metrics(portfolio_values, data['trades'])

    # 准备数据
    dates = portfolio_values['日期']
    total_values = portfolio_values['总资产']
    cumulative_investment = metrics['cumulative_investment']
    daily_returns = metrics['daily_returns']
    drawdown = metrics['drawdown_series']

    # 创建图表
    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    fig.suptitle('定投回测分析报告', fontsize=16, fontweight='bold')

    # 子图1：资产价值曲线
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(dates, total_values, 'b-', linewidth=2, label='总资产')
    ax1.axhline(y=cumulative_investment, color='r', linestyle='--', linewidth=1.5, label='累计投入')
    ax1.fill_between(dates, cumulative_investment, total_values,
                     where=[tv >= cumulative_investment for tv in total_values],
                     alpha=0.3, color='green', label='盈利')
    ax1.fill_between(dates, cumulative_investment, total_values,
                     where=[tv < cumulative_investment for tv in total_values],
                     alpha=0.3, color='red', label='亏损')

    ax1.set_ylabel('金额（元）', fontsize=11)
    ax1.set_title('资产价值曲线', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=9)

    # 格式化x轴
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 添加统计信息
    info_text = f'最终资产: {metrics["final_value"]:,.2f} 元\n'
    info_text += f'累计投入: {metrics["cumulative_investment"]:,.2f} 元\n'
    info_text += f'总收益: {metrics["total_profit"]:+,.2f} 元\n'
    info_text += f'收益率: {metrics["total_return"]:+.2f}%\n'
    info_text += f'最大回撤: {metrics["max_drawdown"]:.2f}%'

    ax1.text(0.02, 0.98, info_text,
             transform=ax1.transAxes,
             fontsize=9,
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    # 子图2：收益率曲线
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(dates, daily_returns, 'g-', linewidth=1.5)
    ax2.axhline(y=0, color='k', linestyle='--', linewidth=1, alpha=0.5)
    ax2.fill_between(dates, 0, daily_returns,
                     where=[r >= 0 for r in daily_returns],
                     alpha=0.3, color='green')
    ax2.fill_between(dates, 0, daily_returns,
                     where=[r < 0 for r in daily_returns],
                     alpha=0.3, color='red')

    ax2.set_ylabel('收益率（%）', fontsize=11)
    ax2.set_title('收益率曲线', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 收益率统计
    max_return = np.max(daily_returns) if len(daily_returns) > 0 else 0
    min_return = np.min(daily_returns) if len(daily_returns) > 0 else 0
    avg_return = np.mean(daily_returns) if len(daily_returns) > 0 else 0

    stats_text = f'最高: {max_return:+.2f}%\n'
    stats_text += f'最低: {min_return:+.2f}%\n'
    stats_text += f'平均: {avg_return:+.2f}%'

    ax2.text(0.02, 0.98, stats_text,
             transform=ax2.transAxes,
             fontsize=9,
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

    # 子图3：回撤曲线
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.fill_between(dates, 0, drawdown, alpha=0.3, color='red')
    ax3.plot(dates, drawdown, 'r-', linewidth=1.5)
    ax3.set_ylabel('回撤（%）', fontsize=11)
    ax3.set_title('回撤曲线', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 子图4：交易记录（如果有）
    ax4 = fig.add_subplot(gs[2, :])
    if data['trades'] is not None and len(data['trades']) > 0:
        trades = data['trades']
        # 标记交易点在资产曲线上
        trade_dates = trades['交易日期']
        trade_values = []
        for td in trade_dates:
            # 找到最接近的日期
            closest_idx = (dates - td).abs().idxmin()
            trade_values.append(portfolio_values.loc[closest_idx, '总资产'])

        # 绘制资产曲线和交易点
        ax4.plot(dates, total_values, 'b-', linewidth=1.5, alpha=0.7, label='总资产')
        ax4.scatter(trade_dates, trade_values, c='red', s=100, zorder=5,
                   marker='^', label='定投点', edgecolors='black', linewidths=1)

        ax4.set_xlabel('日期', fontsize=11)
        ax4.set_ylabel('金额（元）', fontsize=11)
        ax4.set_title(f'交易记录（共 {len(trades)} 次定投）', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3)
        ax4.legend(loc='upper left', fontsize=9)
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')
    else:
        ax4.text(0.5, 0.5, '无交易记录', ha='center', va='center',
                fontsize=12, transform=ax4.transAxes)
        ax4.set_title('交易记录', fontsize=12, fontweight='bold')

    # 保存或显示
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"图表已保存到: {output_path}")

    if show:
        plt.show()
    else:
        plt.close()


def plot_comparison(data_dirs, output_path=None, show=False, title=None):
    """
    绘制多个回测结果的对比图

    Args:
        data_dirs: 回测结果目录列表
        output_path: 输出文件路径
        show: 是否显示图表
        title: 图表标题
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # 加载所有数据
    all_data = []
    labels = []

    for i, data_dir in enumerate(data_dirs):
        try:
            data = load_backtest_data(data_dir)
            portfolio_values = data['portfolio_values']
            metrics = extract_metrics(portfolio_values, data['trades'])

            all_data.append({
                'dates': portfolio_values['日期'],
                'values': portfolio_values['总资产'],
                'metrics': metrics,
                'daily_returns': metrics['daily_returns']
            })

            # 生成标签（使用目录名）
            label = Path(data_dir).name
            # 简化标签
            if 'backtest_' in label:
                label = label.replace('backtest_', '').split('_')[1:]
                label = '_'.join(label)
            labels.append(label)

        except Exception as e:
            print(f"警告: 无法加载 {data_dir}: {e}")
            continue

    if not all_data:
        print("错误: 没有可用的数据")
        return

    # 创建对比图表
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    if title:
        fig.suptitle(title, fontsize=16, fontweight='bold')
    else:
        fig.suptitle('定投策略对比', fontsize=16, fontweight='bold')

    # 子图1：资产价值对比
    ax1 = axes[0]
    colors = plt.cm.tab10(np.linspace(0, 1, len(all_data)))

    for i, data in enumerate(all_data):
        ax1.plot(data['dates'], data['values'],
                linewidth=2, label=labels[i], color=colors[i])

    ax1.set_ylabel('金额（元）', fontsize=12)
    ax1.set_title('资产价值对比', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=10)

    # 格式化x轴
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 子图2：收益率对比
    ax2 = axes[1]

    for i, data in enumerate(all_data):
        dates = data['dates']
        returns = data['daily_returns']
        ax2.plot(dates, returns, linewidth=2, label=labels[i], color=colors[i])

    ax2.axhline(y=0, color='k', linestyle='--', linewidth=1, alpha=0.5)
    ax2.set_ylabel('收益率（%）', fontsize=12)
    ax2.set_xlabel('日期', fontsize=12)
    ax2.set_title('收益率对比', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper left', fontsize=10)

    # 格式化x轴
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 添加对比统计表
    stats_text = "策略对比统计:\n\n"
    stats_text += f"{'策略':<20} {'最终资产':>15} {'收益率':>10} {'最大回撤':>10}\n"
    stats_text += "-" * 60 + "\n"

    for i, (label, data) in enumerate(zip(labels, all_data)):
        m = data['metrics']
        stats_text += f"{label:<20} {m['final_value']:>13.2f} 元  {m['total_return']:>8.2f}%  {m['max_drawdown']:>8.2f}%\n"

    ax2.text(0.98, 0.02, stats_text,
             transform=ax2.transAxes,
             fontsize=8,
             verticalalignment='bottom',
             horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))

    plt.tight_layout()

    # 保存或显示
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"对比图表已保存到: {output_path}")

    if show:
        plt.show()
    else:
        plt.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="回测结果可视化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 绘制单个回测结果
  python plot_backtest.py -d results/backtest_20260116_012811_210014100

  # 绘制多个回测结果进行对比
  python plot_backtest.py -d results/backtest_* -o comparison.png

  # 指定自定义图表标题
  python plot_backtest.py -d results/backtest_* -t "定投策略对比"
        """
    )

    parser.add_argument(
        "-d", "--data-dir",
        type=str,
        required=True,
        help="回测结果目录（支持通配符，如 results/backtest_*）"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        help="输出图片路径（如 output.png）"
    )

    parser.add_argument(
        "-t", "--title",
        type=str,
        help="图表标题"
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="显示图表（需要在GUI环境中使用）"
    )

    args = parser.parse_args()

    try:
        # 尝试导入 matplotlib
        import matplotlib
        matplotlib.use('Agg')  # 使用非交互式后端
        import matplotlib.pyplot as plt
    except ImportError:
        print("错误: matplotlib 未安装")
        print("请运行: pip install matplotlib")
        sys.exit(1)

    # 展开通配符
    data_dirs = glob.glob(args.data_dir)

    if not data_dirs:
        print(f"错误: 找不到匹配的目录: {args.data_dir}")
        sys.exit(1)

    print(f"找到 {len(data_dirs)} 个结果目录")

    # 根据目录数量选择绘制方式
    if len(data_dirs) == 1:
        print(f"绘制单个回测结果: {data_dirs[0]}")
        output_path = args.output or os.path.join(data_dirs[0], "backtest_analysis.png")
        plot_single_backtest(data_dirs[0], output_path=output_path, show=args.show)
    else:
        print(f"绘制 {len(data_dirs)} 个回测结果的对比图")
        output_path = args.output or "backtest_comparison.png"
        plot_comparison(data_dirs, output_path=output_path, show=args.show, title=args.title)


if __name__ == "__main__":
    main()
