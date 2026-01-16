#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金费率数据下载工具

功能：
- 从东方财富网/天天基金网下载基金费率数据
- 支持指定基金代码、输出目录
- 下载申购费率、赎回费率、管理费率、托管费率等信息
- 自动保存为JSON文件
"""

import requests
import json
import os
import argparse
from datetime import datetime
from typing import Optional, Dict, List, Any
from bs4 import BeautifulSoup
import re


class FundFeeDownloader:
    """基金费率数据下载器"""

    def __init__(self, fund_code: str, output_dir: str = "./data"):
        """
        初始化下载器

        Args:
            fund_code: 基金代码
            output_dir: 输出目录
        """
        self.fund_code = fund_code
        self.output_dir = output_dir
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": f"http://fundf10.eastmoney.com/jjfl_{fund_code}.html"
        }

    def _make_request(self, url: str) -> Optional[str]:
        """
        发起HTTP请求

        Args:
            url: 请求URL

        Returns:
            响应文本内容，失败返回None
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return None

    def _parse_subscription_fee(self, html_content: str) -> List[Dict[str, Any]]:
        """
        解析申购费率

        Args:
            html_content: HTML内容

        Returns:
            申购费率列表
        """
        fees = []

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 查找包含"申购费率（前端）"的h4标签
            h4_tags = soup.find_all('h4')
            target_table = None

            for h4 in h4_tags:
                if '申购费率（前端）' in h4.get_text():
                    # 在h4的父元素中查找table
                    parent = h4.parent
                    if parent:
                        target_table = parent.find('table')
                    break

            if target_table:
                # 解析表格
                tbody = target_table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 3:
                            # 第一列：金额区间
                            amount_range = cols[0].get_text(strip=True)
                            # 第三列：包含原费率和优惠费率
                            fee_text = cols[2].get_text(strip=True)

                            # 跳过无效行
                            if not amount_range or amount_range == '---' or '适用金额' in amount_range:
                                continue

                            # 解析费率文本
                            # 格式可能是: "1.50% | 0.15% | 0.15%" 或 "每笔1000元"
                            if '每笔' in fee_text:
                                # 固定费用
                                fee_info = {
                                    "金额区间": amount_range,
                                    "原费率": fee_text,
                                    "优惠费率": fee_text
                                }
                            else:
                                # 百分比费率
                                parts = fee_text.split('|')
                                original_fee = parts[0].strip() if parts else None
                                discount_fee = parts[1].strip() if len(parts) > 1 else None

                                # 移除删除线标记
                                if original_fee and '<' in original_fee:
                                    original_fee = original_fee.split('>')[1] if '>' in original_fee else original_fee

                                fee_info = {
                                    "金额区间": amount_range,
                                    "原费率": self._parse_rate(original_fee)
                                }
                                if discount_fee:
                                    fee_info["优惠费率"] = self._parse_rate(discount_fee)

                            fees.append(fee_info)

        except Exception as e:
            print(f"解析申购费率失败: {e}")

        return fees

    def _parse_redemption_fee(self, html_content: str) -> List[Dict[str, Any]]:
        """
        解析赎回费率

        Args:
            html_content: HTML内容

        Returns:
            赎回费率列表
        """
        fees = []

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 查找包含"赎回费率"的h4标签（不包含a标签）
            h4_tags = soup.find_all('h4')
            target_table = None

            for h4 in h4_tags:
                h4_text = h4.get_text()
                # 查找"赎回费率"但不包含其他复杂的文本
                if '赎回费率' in h4_text and len(h4_text.strip()) < 20:
                    # 在h4的父元素中查找table
                    parent = h4.parent
                    if parent:
                        target_table = parent.find('table')
                    break

            if target_table:
                # 解析表格
                tbody = target_table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 3:
                            # 第一列：金额（通常是---）
                            # 第二列：持有期限
                            # 第三列：赎回费率
                            holding_period = cols[1].get_text(strip=True)
                            fee_rate = cols[2].get_text(strip=True)

                            # 跳过无效行
                            if not holding_period or holding_period == '---' or '适用期限' in holding_period:
                                continue

                            fee_info = {
                                "持有期限": holding_period,
                                "费率": self._parse_rate(fee_rate)
                            }
                            fees.append(fee_info)

        except Exception as e:
            print(f"解析赎回费率失败: {e}")

        return fees

    def _parse_operating_fees(self, html_content: str) -> Dict[str, float]:
        """
        解析运作费用（管理费、托管费等）

        Args:
            html_content: HTML内容

        Returns:
            运作费用字典
        """
        fees = {
            "管理费率": None,
            "托管费率": None,
            "销售服务费率": None
        }

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 查找包含运作费用的信息
            # 可能在特定class的div或表格中
            text_content = soup.get_text()

            # 使用正则表达式提取费率
            # 管理费率：通常格式为 "管理费：1.20%" 或 "管理费率 1.20%/年"
            management_pattern = r'管理费[^0-9.]*([0-9.]+)%'
            custody_pattern = r'托管费[^0-9.]*([0-9.]+)%'
            service_pattern = r'销售服务费[^0-9.]*([0-9.]+)%'

            management_match = re.search(management_pattern, text_content)
            if management_match:
                fees["管理费率"] = float(management_match.group(1)) / 100

            custody_match = re.search(custody_pattern, text_content)
            if custody_match:
                fees["托管费率"] = float(custody_match.group(1)) / 100

            service_match = re.search(service_pattern, text_content)
            if service_match:
                fees["销售服务费率"] = float(service_match.group(1)) / 100

        except Exception as e:
            print(f"解析运作费用失败: {e}")

        return fees

    def _parse_rate(self, rate_str: str) -> Optional[float]:
        """
        解析费率字符串

        Args:
            rate_str: 费率字符串，如 "1.20%" 或 "0.12%"

        Returns:
            费率浮点数（如 0.012），失败返回None
        """
        if not rate_str or rate_str == '-' or rate_str == '--':
            return None

        try:
            # 移除百分号
            rate_str = rate_str.replace('%', '').strip()
            # 转换为浮点数
            rate = float(rate_str)
            # 转换为小数形式（百分数除以100）
            return rate / 100
        except (ValueError, AttributeError):
            return None

    def _get_fund_name(self, html_content: str) -> Optional[str]:
        """
        获取基金名称

        Args:
            html_content: HTML内容

        Returns:
            基金名称，失败返回None
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 查找基金名称，通常在页面标题或特定的div中
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                # 提取基金名称（通常在标题中）
                if '（' in title_text:
                    fund_name = title_text.split('（')[0].strip()
                    return fund_name
                elif '(' in title_text:
                    fund_name = title_text.split('(')[0].strip()
                    return fund_name

        except Exception as e:
            print(f"获取基金名称失败: {e}")

        return None

    def download_fee_info(self) -> Dict[str, Any]:
        """
        下载基金费率信息

        Returns:
            包含费率信息的字典
        """
        print(f"开始下载基金 {self.fund_code} 的费率信息...")

        # 构造费率页面URL
        fee_url = f"http://fundf10.eastmoney.com/jjfl_{self.fund_code}.html"

        # 请求页面
        html_content = self._make_request(fee_url)
        if not html_content:
            print("获取费率页面失败")
            return {}

        # 解析各项费率
        fund_name = self._get_fund_name(html_content)
        subscription_fees = self._parse_subscription_fee(html_content)
        redemption_fees = self._parse_redemption_fee(html_content)
        operating_fees = self._parse_operating_fees(html_content)

        # 构造结果
        result = {
            "基金代码": self.fund_code,
            "基金名称": fund_name,
            "申购费率": subscription_fees,
            "赎回费率": redemption_fees,
            "管理费率": operating_fees.get("管理费率"),
            "托管费率": operating_fees.get("托管费率"),
            "销售服务费率": operating_fees.get("销售服务费率"),
            "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        print(f"费率信息下载完成！")
        return result

    def download_overview(self) -> Dict[str, Any]:
        """
        下载基金基本概况信息

        Returns:
            包含基金概况的字典
        """
        print(f"开始下载基金 {self.fund_code} 的基本概况...")

        # 构造概况页面URL
        overview_url = f"http://fundf10.eastmoney.com/jbgk_{self.fund_code}.html"

        # 请求页面
        html_content = self._make_request(overview_url)
        if not html_content:
            print("获取概况页面失败")
            return {}

        result = {
            "基金代码": self.fund_code,
            "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 查找基金概况信息
            # 通常在特定的div或表格中
            info_items = soup.find_all(['div', 'td', 'th'])

            for item in info_items:
                text = item.get_text(strip=True)
                # 查找关键信息
                if '基金类型' in text and '基金类型' not in result:
                    # 尝试提取基金类型
                    type_match = re.search(r'基金类型[：:]\s*([^\s]+)', text)
                    if type_match:
                        result["基金类型"] = type_match.group(1)
                elif '成立日期' in text and '成立日期' not in result:
                    date_match = re.search(r'成立日期[：:]\s*([0-9-]+)', text)
                    if date_match:
                        result["成立日期"] = date_match.group(1)
                elif '管理费率' in text and '管理费率' not in result:
                    rate_match = re.search(r'管理费率[：:]\s*([0-9.]+)%', text)
                    if rate_match:
                        result["管理费率"] = float(rate_match.group(1)) / 100
                elif '托管费率' in text and '托管费率' not in result:
                    rate_match = re.search(r'托管费率[：:]\s*([0-9.]+)%', text)
                    if rate_match:
                        result["托管费率"] = float(rate_match.group(1)) / 100

            # 尝试从标题获取基金名称
            title = soup.find('title')
            if title and '基金名称' not in result:
                title_text = title.get_text()
                if '（' in title_text:
                    result["基金名称"] = title_text.split('（')[0].strip()

        except Exception as e:
            print(f"解析基金概况失败: {e}")

        print(f"基金概况下载完成！")
        return result

    def _save_to_json(self, data: Dict[str, Any], filename: str):
        """
        保存数据到JSON文件

        Args:
            data: 要保存的数据
            filename: 文件名
        """
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)

        # 构造文件路径
        filepath = os.path.join(self.output_dir, filename)

        # 保存为JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"数据已保存到: {filepath}")

    def download(self, save: bool = True) -> Dict[str, Any]:
        """
        下载基金费率和概况信息

        Args:
            save: 是否保存到文件

        Returns:
            包含费率和概况信息的字典
        """
        # 下载费率信息
        fee_info = self.download_fee_info()

        # 下载概况信息（可能包含管理费、托管费等）
        overview_info = self.download_overview()

        # 合并信息
        result = {
            **fee_info,
            **overview_info
        }

        # 如果费率解析失败，尝试从概况中获取
        if not result.get("管理费率") and overview_info.get("管理费率"):
            result["管理费率"] = overview_info["管理费率"]
        if not result.get("托管费率") and overview_info.get("托管费率"):
            result["托管费率"] = overview_info["托管费率"]

        # 打印信息
        print("\n=== 费率信息摘要 ===")
        print(f"基金代码: {result.get('基金代码')}")
        print(f"基金名称: {result.get('基金名称')}")
        print(f"申购费率档位: {len(result.get('申购费率', []))} 个")
        print(f"赎回费率档位: {len(result.get('赎回费率', []))} 个")
        print(f"管理费率: {result.get('管理费率', 'N/A')}")
        print(f"托管费率: {result.get('托管费率', 'N/A')}")
        print(f"销售服务费率: {result.get('销售服务费率', 'N/A')}")

        # 保存到文件
        if save:
            filename = f"fund_{self.fund_code}_fee.json"
            self._save_to_json(result, filename)

            # 同时保存概况信息
            overview_filename = f"fund_{self.fund_code}_overview.json"
            self._save_to_json(overview_info, overview_filename)

        return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="下载基金费率数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载基金210014的费率数据
  python fund_fee_downloader.py -c 210014

  # 指定输出目录
  python fund_fee_downloader.py -c 210014 -o ./my_data
        """
    )

    parser.add_argument(
        "-c", "--code",
        type=str,
        required=True,
        help="基金代码 (例如: 210014)"
    )

    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="./data",
        help="输出目录 (默认: ./data)"
    )

    args = parser.parse_args()

    # 创建下载器并下载数据
    downloader = FundFeeDownloader(args.code, args.output_dir)
    result = downloader.download()

    if result:
        # 显示详细费率信息
        if result.get('申购费率'):
            print("\n=== 申购费率详情 ===")
            for fee in result['申购费率']:
                print(f"  {fee}")

        if result.get('赎回费率'):
            print("\n=== 赎回费率详情 ===")
            for fee in result['赎回费率']:
                print(f"  {fee}")


if __name__ == "__main__":
    main()
