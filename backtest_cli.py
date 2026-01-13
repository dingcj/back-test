#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投资组合回测命令行接口

示例用法：
    # 单基金月定投
    python backtest_cli.py -p "210014:1.0" -a 1000 -f monthly --day-of-month 15 -s 2023-01-01 -e 2024-01-01

    # 多基金组合月定投（含分红）
    python backtest_cli.py -p "210014:0.5,110022:0.3,013308:0.2" -a 1000 -f monthly --day-of-month 15 -s 2023-01-01 -e 2024-01-01

    # 周定投
    python backtest_cli.py -p "210014:1.0" -a 500 -f weekly --day-of-week 1 -s 2023-10-01 -e 2024-01-01
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from fund_data_manager import FundDataManager, parse_portfolio_input
from portfolio_backtester import InvestmentSchedule, BacktestEngine


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="基金投资组合回测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 单基金月定投
  python backtest_cli.py -p "210014:1.0" -a 1000 -f monthly --day-of-month 15 -s 2023-01-01 -e 2024-01-01

  # 多基金组合月定投
  python backtest_cli.py -p "210014:0.5,110022:0.3,013308:0.2" -a 1000 -f monthly --day-of-month 15 -s 2023-01-01 -e 2024-01-01

  # 周定投（每周一）
  python backtest_cli.py -p "210014:0.6,013308:0.4" -a 500 -f weekly --day-of-week 1 -s 2023-10-01 -e 2024-01-01

  # 日定投
  python backtest_cli.py -p "210014:1.0" -a 200 -f daily -s 2023-12-01 -e 2024-01-01
        """
    )

    parser.add_argument(
        "-p", "--portfolio",
        type=str,
        required=True,
        help="投资组合，格式: 基金代码:比例,... (例如: 210014:0.5,110022:0.3,013308:0.2)"
    )

    parser.add_argument(
        "-a", "--amount",
        type=float,
        default=1000,
        help="每次定投金额（默认: 1000元）"
    )

    parser.add_argument(
        "-f", "--frequency",
        type=str,
        choices=['daily', 'weekly', 'monthly'],
        default='monthly',
        help="定投频率（默认: monthly）"
    )

    parser.add_argument(
        "--day-of-week",
        type=int,
        choices=range(1, 8),
        help="周定投：星期几（1-7，1=周一）"
    )

    parser.add_argument(
        "--day-of-month",
        type=int,
        choices=range(1, 32),
        help="月定投：每月几号（1-31）"
    )

    parser.add_argument(
        "-s", "--start-date",
        type=str,
        required=True,
        help="回测开始日期（格式: YYYY-MM-DD）"
    )

    parser.add_argument(
        "-e", "--end-date",
        type=str,
        required=True,
        help="回测结束日期（格式: YYYY-MM-DD）"
    )

    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="./results",
        help="结果输出目录（默认: ./results）"
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="基金数据目录（默认: ./data）"
    )

    parser.add_argument(
        "--force-download",
        action="store_true",
        help="强制重新下载数据（忽略缓存）"
    )

    args = parser.parse_args()

    try:
        # 验证参数
        if args.frequency == 'weekly' and args.day_of_week is None:
            parser.error("周定投需要指定 --day-of-week 参数")

        if args.frequency == 'monthly' and args.day_of_month is None:
            parser.error("月定投需要指定 --day-of-month 参数")

        # 解析投资组合配置
        print("解析投资组合配置...")
        allocations = parse_portfolio_input(args.portfolio)
        print(f"投资组合: {allocations}\n")

        # 创建投资计划
        schedule = InvestmentSchedule(
            frequency=args.frequency,
            amount=args.amount,
            day_of_week=args.day_of_week,
            day_of_month=args.day_of_month
        )

        # 创建数据管理器
        data_manager = FundDataManager(args.data_dir)

        # 创建回测引擎
        engine = BacktestEngine(allocations, schedule, data_manager)

        # 运行回测
        result = engine.run(args.start_date, args.end_date)

        # 创建输出目录
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成结果文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        portfolio_str = "_".join([f"{code}{int(ratio*100)}" for code, ratio in allocations.items()])
        result_subdir = output_dir / f"backtest_{timestamp}_{portfolio_str}"
        result_subdir.mkdir(exist_ok=True)

        # 保存结果文件
        print("\n保存结果文件...")

        # 1. 交易记录
        trades_file = result_subdir / "trades.csv"
        result.save_trades(str(trades_file))

        # 2. 组合价值历史
        values_file = result_subdir / "portfolio_values.csv"
        result.save_portfolio_values(str(values_file))

        # 3. 绩效报告
        report = result.generate_report()
        report_file = result_subdir / "report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\n绩效报告:")
        print(report)

        print(f"\n结果已保存到: {result_subdir}")

        # 保存控制台日志（如果需要）
        # TODO: 可以添加将控制台输出重定向到文件的功能

    except ValueError as e:
        print(f"参数错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"回测失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
