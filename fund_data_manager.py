#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金数据管理器

功能：
- 管理多基金数据获取和缓存
- 解析分红数据
- 批量加载多基金数据
"""

import os
import pandas as pd
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from fund_data_downloader import FundDataDownloader


class FundDataManager:
    """管理多基金数据获取和缓存"""

    def __init__(self, data_dir: str = "./data"):
        """
        初始化数据管理器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        self.cache = {}  # 内存缓存 {fund_code: DataFrame}

    def get_fund_data(self, fund_code: str, force_download: bool = False) -> pd.DataFrame:
        """
        获取基金数据（带缓存）

        优先级：
        1. 检查内存缓存
        2. 检查本地文件
        3. 下载新数据

        Args:
            fund_code: 基金代码
            force_download: 是否强制重新下载

        Returns:
            包含净值数据的DataFrame
        """
        # 1. 检查内存缓存
        if not force_download and fund_code in self.cache:
            print(f"使用缓存数据: {fund_code}")
            return self.cache[fund_code]

        # 2. 检查本地文件
        if not force_download:
            cached_file = self._find_cached_file(fund_code)
            if cached_file:
                print(f"加载本地文件: {cached_file}")
                df = pd.read_csv(cached_file, encoding='utf-8-sig')
                df['净值日期'] = pd.to_datetime(df['净值日期'])
                self.cache[fund_code] = df
                return df

        # 3. 下载新数据
        print(f"下载基金 {fund_code} 的数据...")
        downloader = FundDataDownloader(fund_code, self.data_dir)
        df = downloader.download(save=True)

        if df.empty:
            raise ValueError(f"基金 {fund_code} 没有获取到数据")

        self.cache[fund_code] = df
        return df

    def _find_cached_file(self, fund_code: str) -> Optional[str]:
        """
        查找缓存的CSV文件

        Args:
            fund_code: 基金代码

        Returns:
            文件路径，如果不存在则返回None
        """
        if not os.path.exists(self.data_dir):
            return None

        # 查找匹配的文件
        pattern = f"fund_{fund_code}_netvalue_"
        for filename in os.listdir(self.data_dir):
            if filename.startswith(pattern) and filename.endswith('.csv'):
                return os.path.join(self.data_dir, filename)

        return None

    def parse_dividend(self, dividend_str: str) -> Optional[Dict]:
        """
        解析分红字符串

        支持的格式：
        - "每份派现金0.05元" - 现金分红
        - "每份派基金份额0.05份" - 份额分红
        - "" 或 None - 无分红

        Args:
            dividend_str: 分红字符串

        Returns:
            包含分红信息的字典，如无分红则返回None
            {
                'type': 'cash',  # 'cash' 或 'share'
                'amount_per_unit': 0.05,  # 每份分红金额/份额
                'raw_text': '每份派现金0.05元'
            }
        """
        if not dividend_str or pd.isna(dividend_str):
            return None

        dividend_str = dividend_str.strip()
        if not dividend_str:
            return None

        # 匹配现金分红
        cash_pattern = r'每份派现金([\d.]+)元'
        cash_match = re.search(cash_pattern, dividend_str)
        if cash_match:
            return {
                'type': 'cash',
                'amount_per_unit': float(cash_match.group(1)),
                'raw_text': dividend_str
            }

        # 匹配份额分红
        share_pattern = r'每份派基金份额([\d.]+)份'
        share_match = re.search(share_pattern, dividend_str)
        if share_match:
            return {
                'type': 'share',
                'amount_per_unit': float(share_match.group(1)),
                'raw_text': dividend_str
            }

        # 未识别的格式
        return {
            'type': 'unknown',
            'amount_per_unit': 0,
            'raw_text': dividend_str
        }

    def get_multi_fund_data(self, fund_codes: List[str], force_download: bool = False) -> Dict[str, pd.DataFrame]:
        """
        批量加载多基金数据

        Args:
            fund_codes: 基金代码列表
            force_download: 是否强制重新下载

        Returns:
            {fund_code: DataFrame} 字典
        """
        fund_data = {}
        for code in fund_codes:
            try:
                df = self.get_fund_data(code, force_download)
                fund_data[code] = df
            except Exception as e:
                print(f"警告: 无法加载基金 {code} 的数据: {e}")
                raise

        return fund_data

    def get_common_trading_days(self, fund_data: Dict[str, pd.DataFrame]) -> List[datetime]:
        """
        获取所有基金共同的交易日

        Args:
            fund_data: {fund_code: DataFrame} 字典

        Returns:
            排序后的交易日列表
        """
        if not fund_data:
            return []

        # 获取所有基金的交易日
        common_dates = None
        for fund_code, df in fund_data.items():
            dates = set(df['净值日期'].dt.date)
            if common_dates is None:
                common_dates = dates
            else:
                common_dates = common_dates.intersection(dates)

        # 转换为datetime并排序
        trading_days = sorted([datetime.combine(d, datetime.min.time()) for d in common_dates])

        return trading_days

    def get_nav_for_date(self, fund_code: str, date: datetime, fund_data: Dict[str, pd.DataFrame]) -> Optional[float]:
        """
        获取指定日期的净值

        Args:
            fund_code: 基金代码
            date: 日期
            fund_data: 基金数据字典

        Returns:
            净值，如果该日期没有数据则返回None
        """
        if fund_code not in fund_data:
            return None

        df = fund_data[fund_code]
        row = df[df['净值日期'].dt.date == date.date()]

        if row.empty:
            return None

        return row.iloc[0]['单位净值']

    def get_dividend_for_date(self, fund_code: str, date: datetime, fund_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
        """
        获取指定日期的分红信息

        Args:
            fund_code: 基金代码
            date: 日期
            fund_data: 基金数据字典

        Returns:
            分红信息字典，如果没有分红则返回None
        """
        if fund_code not in fund_data:
            return None

        df = fund_data[fund_code]
        row = df[df['净值日期'].dt.date == date.date()]

        if row.empty:
            return None

        # 兼容旧数据：如果没有"分红送配"列，返回None
        if '分红送配' not in row.columns:
            return None

        dividend_str = row.iloc[0]['分红送配']
        return self.parse_dividend(dividend_str)

    def get_purchase_status(self, fund_code: str, date: datetime, fund_data: Dict[str, pd.DataFrame]) -> Optional[str]:
        """
        获取指定日期的申购状态

        Args:
            fund_code: 基金代码
            date: 日期
            fund_data: 基金数据字典

        Returns:
            申购状态字符串，如"开放申购"、"暂停申购"等
        """
        if fund_code not in fund_data:
            return None

        df = fund_data[fund_code]
        row = df[df['净值日期'].dt.date == date.date()]

        if row.empty:
            return None

        # 兼容旧数据：如果没有"申购状态"列，返回"开放申购"
        if '申购状态' not in row.columns:
            return "开放申购"

        return row.iloc[0]['申购状态']

    def can_purchase_all(self, fund_codes: List[str], date: datetime, fund_data: Dict[str, pd.DataFrame]) -> Tuple[bool, List[str]]:
        """
        检查所有基金在指定日期是否都可以申购

        Args:
            fund_codes: 基金代码列表
            date: 日期
            fund_data: 基金数据字典

        Returns:
            (是否都可以申购, 不能申购的基金列表)
        """
        cannot_purchase = []

        for code in fund_codes:
            status = self.get_purchase_status(code, date, fund_data)
            if status and "暂停" in status or "封闭" in status or "限制" in status:
                cannot_purchase.append(f"{code}({status})")

        return len(cannot_purchase) == 0, cannot_purchase


def parse_portfolio_input(input_str: str) -> Dict[str, float]:
    """
    解析投资组合输入

    格式: "基金代码:比例,基金代码:比例,..."
    例如: "210014:0.5,110022:0.3,013308:0.2"

    Args:
        input_str: 投资组合字符串

    Returns:
        {fund_code: proportion} 字典

    Raises:
        ValueError: 如果格式错误或比例总和不为1
    """
    allocations = {}
    parts = input_str.split(',')

    for part in parts:
        if ':' not in part:
            raise ValueError(f"格式错误: '{part}'，应为 '基金代码:比例'")

        code, prop = part.split(':', 1)
        code = code.strip()
        prop = prop.strip()

        # 验证基金代码（6位数字）
        if not re.match(r'^\d{6}$', code):
            raise ValueError(f"基金代码格式错误: '{code}'，应为6位数字")

        try:
            prop_value = float(prop)
        except ValueError:
            raise ValueError(f"比例格式错误: '{prop}'，应为数字")

        if prop_value <= 0:
            raise ValueError(f"比例必须大于0: '{code}:{prop}'")

        allocations[code] = prop_value

    # 验证总和
    total = sum(allocations.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"比例总和必须为1.0，当前总和: {total:.2f}")

    return allocations


if __name__ == "__main__":
    # 测试代码
    manager = FundDataManager("./data")

    # 测试获取单个基金数据
    print("测试获取基金数据:")
    df = manager.get_fund_data("210014")
    print(f"基金210014: {len(df)} 条记录")
    print(df.head(3))

    # 测试解析分红
    print("\n测试解析分红:")
    test_cases = [
        "每份派现金0.05元",
        "每份派基金份额0.1份",
        "",
        None
    ]
    for case in test_cases:
        result = manager.parse_dividend(case)
        print(f"输入: '{case}' => {result}")

    # 测试投资组合解析
    print("\n测试投资组合解析:")
    test_portfolio = "210014:0.5,110022:0.3,013308:0.2"
    allocations = parse_portfolio_input(test_portfolio)
    print(f"投资组合: {allocations}")
