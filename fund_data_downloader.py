#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金历史净值数据下载工具

功能：
- 从东方财富网/天天基金网下载基金历史净值数据
- 支持指定基金代码、起始日期、输出目录
- 显示下载进度
- 自动保存为CSV文件，文件名包含基金代码
"""

import requests
import pandas as pd
import os
import argparse
from datetime import datetime
from typing import Optional


class FundDataDownloader:
    """基金历史净值数据下载器"""

    def __init__(self, fund_code: str, output_dir: str = "./data"):
        """
        初始化下载器

        Args:
            fund_code: 基金代码
            output_dir: 输出目录
        """
        self.fund_code = fund_code
        self.output_dir = output_dir
        self.base_url = "http://fund.eastmoney.com/f10/F10DataApi.aspx"

    def _make_request(self, page: int = 1, per_page: int = 200, sdate: str = "", edate: str = "") -> dict:
        """
        发起API请求获取数据

        Args:
            page: 页码
            per_page: 每页数据条数
            sdate: 起始日期
            edate: 结束日期

        Returns:
            API返回的JSON数据
        """
        params = {
            "type": "lsjz",
            "code": self.fund_code,
            "page": page,
            "per": per_page,
            "sdate": sdate,
            "edate": edate,
            "rt": int(datetime.now().timestamp() * 1000)
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": f"http://fundf10.eastmoney.com/jjjz_{self.fund_code}.html"
        }

        try:
            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            # 打印调试信息
            if page == 1:
                print(f"API URL: {response.url}")

            # 尝试解析数据
            try:
                text = response.text

                # 首先尝试JSON格式
                try:
                    data = response.json()
                    if page == 1:
                        print(f"返回数据键: {list(data.keys())}")
                    return data
                except ValueError:
                    pass

                # 如果不是JSON，尝试解析JavaScript变量格式: var apidata={...};
                if "var apidata=" in text:
                    import re
                    import json
                    import html

                    # 提取大括号内的内容
                    match = re.search(r'var apidata=\{(.+?)\};', text, re.DOTALL)
                    if match:
                        content = match.group(1)

                        # 转换JavaScript对象字面量为JSON
                        # 1. 给属性名添加双引号
                        content = re.sub(r"(\w+):", r'"\1":', content)

                        # 2. 处理HTML字符串中的转义问题
                        # 先提取HTML字符串内容
                        html_match = re.search(r'"content":"(.+?)"', content, re.DOTALL)
                        if html_match:
                            html_content = html_match.group(1)
                            # 转义HTML中的特殊字符
                            html_content = html_content.replace('\\', '\\\\').replace('"', '\\"')
                            content = re.sub(r'"content":".+?"', f'"content":"{html_content}"', content, count=1, flags=re.DOTALL)

                        try:
                            json_str = "{" + content + "}"
                            data = json.loads(json_str)

                            # 解码HTML实体
                            if 'content' in data and data['content']:
                                # 使用HTML解码
                                data['content'] = html.unescape(data['content'])

                            if page == 1:
                                print(f"返回数据键: {list(data.keys())}")
                            return data
                        except json.JSONDecodeError as je:
                            if page == 1:
                                print(f"JSON解析失败: {je}")
                                print(f"尝试解析的内容前200字符: {content[:200]}")

                if page == 1:
                    print(f"无法解析响应，前500字符: {text[:500]}")
                return {}

            except Exception as e:
                print(f"解析失败: {e}")
                return {}

        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return {}

    def _parse_data(self, data: dict) -> pd.DataFrame:
        """
        解析API返回的数据

        Args:
            data: API返回的数据

        Returns:
            包含净值数据的DataFrame
        """
        if not data or "content" not in data:
            return pd.DataFrame()

        content = data["content"]
        if not content:
            return pd.DataFrame()

        # 使用BeautifulSoup解析HTML表格
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')

            # 查找表格中的所有行
            rows = soup.find_all('tr')

            records = []
            for row in rows[1:]:  # 跳过表头
                cols = row.find_all('td')
                if len(cols) >= 4:
                    # 提取文本内容并清理
                    def clean_text(element):
                        if element:
                            text = element.get_text(strip=True)
                            # 移除可能的换行符和多余空格
                            return text.replace('\n', '').replace('\r', '')
                        return ""

                    record = {
                        "净值日期": clean_text(cols[0]),
                        "单位净值": self._parse_number(clean_text(cols[1])),
                        "累计净值": self._parse_number(clean_text(cols[2])),
                        "日增长率(%)": clean_text(cols[3]),
                        "申购状态": clean_text(cols[4]) if len(cols) > 4 else "",
                        "赎回状态": clean_text(cols[5]) if len(cols) > 5 else "",
                        "分红送配": clean_text(cols[6]) if len(cols) > 6 else ""
                    }
                    records.append(record)

        except ImportError:
            # 如果没有BeautifulSoup，使用正则表达式解析
            import re
            pattern = r'<tr>(.*?)</tr>'
            rows = re.findall(pattern, content, re.DOTALL)

            records = []
            for row in rows[1:]:  # 跳过表头
                cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                if len(cols) >= 4:
                    # 清理HTML标签和文本
                    def clean_html(text):
                        # 移除HTML标签
                        text = re.sub(r'<[^>]+>', '', text)
                        return text.strip().replace('\n', '').replace('\r', '')

                    record = {
                        "净值日期": clean_html(cols[0]),
                        "单位净值": self._parse_number(clean_html(cols[1])),
                        "累计净值": self._parse_number(clean_html(cols[2])),
                        "日增长率(%)": clean_html(cols[3]),
                        "申购状态": clean_html(cols[4]) if len(cols) > 4 else "",
                        "赎回状态": clean_html(cols[5]) if len(cols) > 5 else "",
                        "分红送配": clean_html(cols[6]) if len(cols) > 6 else ""
                    }
                    records.append(record)

        df = pd.DataFrame(records)
        if not df.empty:
            df["净值日期"] = pd.to_datetime(df["净值日期"], errors="coerce")
            df = df.sort_values("净值日期", ascending=False).reset_index(drop=True)
            # 清理日增长率（去除百分号和特殊字符）
            df["日增长率(%)"] = df["日增长率(%)"].str.replace("%", "").str.replace(" ", "").replace("", None)
            df["日增长率(%)"] = pd.to_numeric(df["日增长率(%)"], errors="coerce")

        return df

    def _parse_number(self, text: str) -> Optional[float]:
        """解析数字字符串"""
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def download(self, save: bool = True) -> pd.DataFrame:
        """
        下载基金历史净值数据

        Args:
            save: 是否保存到文件

        Returns:
            包含净值数据的DataFrame
        """
        all_data = []
        page = 1
        total_records = 0
        total_pages = None
        all_records = None

        print(f"开始下载基金 {self.fund_code} 的历史净值数据...")

        while True:
            data = self._make_request(page=page)

            if not data or "content" not in data:
                break

            # 解析当前页数据
            df = self._parse_data(data)

            if df.empty:
                break

            all_data.append(df)
            total_records += len(df)

            # 获取总页数和总记录数
            if total_pages is None:
                # 尝试多种可能的字段名
                for key in ["pages", "allPages", "all_pages"]:
                    if key in data:
                        total_pages = int(data[key])
                        break

                for key in ["totalRecords", "all_records", "total"]:
                    if key in data:
                        all_records = int(data[key])
                        break

                if total_pages:
                    print(f"总共 {total_pages} 页数据")
                elif all_records:
                    print(f"总共约 {all_records} 条记录")

            # 显示进度
            if total_pages:
                print(f"正在下载: 第 {page}/{total_pages} 页, 已获取 {total_records} 条记录", end="\r")
            else:
                print(f"正在下载: 第 {page} 页, 已获取 {total_records} 条记录", end="\r")

            # 判断是否还有下一页
            # 如果有总页数信息，使用总页数判断
            if total_pages and page >= total_pages:
                break

            # 如果当前页数据为空，说明没有更多数据了
            if len(df) == 0:
                break

            page += 1
            # 防止无限循环
            if page > 500:
                print("警告: 已达到最大页数限制(500页)")
                break

        print()  # 换行

        if not all_data:
            print("未获取到任何数据")
            return pd.DataFrame()

        # 合并所有数据
        result_df = pd.concat(all_data, ignore_index=True)

        print(f"下载完成! 共获取 {len(result_df)} 条记录")
        if not result_df.empty:
            print(f"数据范围: {result_df['净值日期'].min()} 至 {result_df['净值日期'].max()}")

        # 保存到文件
        if save:
            self._save_to_file(result_df)

        return result_df

    def _save_to_file(self, df: pd.DataFrame):
        """
        保存数据到CSV文件

        Args:
            df: 要保存的数据
        """
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)

        # 生成文件名（包含数据起止时间）
        start_date = df['净值日期'].max().strftime("%Y%m%d")
        end_date = df['净值日期'].min().strftime("%Y%m%d")
        filename = f"fund_{self.fund_code}_netvalue_{end_date}_to_{start_date}.csv"
        filepath = os.path.join(self.output_dir, filename)

        # 保存为CSV
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        print(f"数据已保存到: {filepath}")

        # 尝试保存为Excel格式
        try:
            excel_filepath = filepath.replace(".csv", ".xlsx")
            df.to_excel(excel_filepath, index=False, engine="openpyxl")
            print(f"数据已保存到: {excel_filepath}")
        except ImportError:
            print("提示: 未安装openpyxl模块，无法保存Excel格式。如需Excel格式，请运行: pip install openpyxl")
        except Exception as e:
            print(f"保存Excel文件失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="下载基金历史净值数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载基金210014的所有历史净值数据
  python fund_data_downloader.py -c 210014

  # 指定输出目录
  python fund_data_downloader.py -c 210014 -o ./my_data
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
    downloader = FundDataDownloader(args.code, args.output_dir)
    df = downloader.download()

    if not df.empty:
        # 显示数据预览
        print("\n数据预览:")
        print(df.head(10).to_string(index=False))

        # 显示统计信息
        print(f"\n统计信息:")
        print(f"  总记录数: {len(df)}")
        print(f"  单位净值范围: {df['单位净值'].min():.4f} - {df['单位净值'].max():.4f}")


if __name__ == "__main__":
    main()
