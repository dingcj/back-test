#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
费率下载器测试脚本

测试基金费率下载器的各项功能
"""

import os
import json
from fund_fee_downloader import FundFeeDownloader


def test_download_fee_info():
    """测试费率下载功能"""
    print("\n" + "="*60)
    print("测试1: 下载基金费率信息")
    print("="*60)

    # 使用一个真实的基金代码进行测试
    fund_code = "210014"  # 这是一个常见的基金代码
    output_dir = "./test_data"

    # 创建下载器
    downloader = FundFeeDownloader(fund_code, output_dir)

    # 下载费率信息
    result = downloader.download_fee_info()

    # 验证结果
    print("\n验证结果:")
    if result:
        print(f"✓ 成功获取费率信息")
        print(f"  - 基金代码: {result.get('基金代码')}")
        print(f"  - 基金名称: {result.get('基金名称')}")
        print(f"  - 申购费率数量: {len(result.get('申购费率', []))}")
        print(f"  - 赎回费率数量: {len(result.get('赎回费率', []))}")
        print(f"  - 管理费率: {result.get('管理费率')}")
        print(f"  - 托管费率: {result.get('托管费率')}")
        print(f"  - 销售服务费率: {result.get('销售服务费率')}")

        # 检查是否有申购费率数据
        if result.get('申购费率'):
            print("\n✓ 成功解析申购费率:")
            for fee in result['申购费率'][:3]:  # 只显示前3个
                print(f"    {fee}")

        # 检查是否有赎回费率数据
        if result.get('赎回费率'):
            print("\n✓ 成功解析赎回费率:")
            for fee in result['赎回费率'][:3]:  # 只显示前3个
                print(f"    {fee}")

        return True
    else:
        print("✗ 未能获取费率信息")
        return False


def test_save_to_json():
    """测试JSON保存功能"""
    print("\n" + "="*60)
    print("测试2: 保存为JSON文件")
    print("="*60)

    fund_code = "210014"
    output_dir = "./test_data"

    downloader = FundFeeDownloader(fund_code, output_dir)
    result = downloader.download_fee_info()

    if result:
        # 保存为JSON
        filename = f"fund_{fund_code}_fee_test.json"
        downloader._save_to_json(result, filename)

        # 验证文件是否创建
        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            print(f"✓ 文件已创建: {filepath}")

            # 验证文件内容
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)

            print(f"✓ 文件可正常读取")
            print(f"  - JSON键数量: {len(loaded_data)}")

            # 验证数据完整性
            if loaded_data.get('基金代码') == fund_code:
                print(f"✓ 基金代码匹配")
            if loaded_data.get('申购费率'):
                print(f"✓ 申购费率数据完整")
            if loaded_data.get('赎回费率'):
                print(f"✓ 赎回费率数据完整")

            return True
        else:
            print(f"✗ 文件未创建: {filepath}")
            return False
    else:
        print("✗ 未能获取数据用于保存")
        return False


def test_download_overview():
    """测试基金概况下载"""
    print("\n" + "="*60)
    print("测试3: 下载基金基本概况")
    print("="*60)

    fund_code = "210014"
    output_dir = "./test_data"

    downloader = FundFeeDownloader(fund_code, output_dir)
    result = downloader.download_overview()

    print("\n验证结果:")
    if result:
        print(f"✓ 成功获取基金概况")
        print(f"  - 基金代码: {result.get('基金代码')}")
        print(f"  - 基金名称: {result.get('基金名称')}")
        print(f"  - 基金类型: {result.get('基金类型', 'N/A')}")
        print(f"  - 成立日期: {result.get('成立日期', 'N/A')}")
        print(f"  - 管理费率: {result.get('管理费率', 'N/A')}")
        print(f"  - 托管费率: {result.get('托管费率', 'N/A')}")
        return True
    else:
        print("✗ 未能获取基金概况")
        return False


def test_full_download():
    """测试完整下载流程"""
    print("\n" + "="*60)
    print("测试4: 完整下载流程（包含保存）")
    print("="*60)

    fund_code = "210014"
    output_dir = "./test_data"

    downloader = FundFeeDownloader(fund_code, output_dir)
    result = downloader.download(save=True)

    print("\n验证结果:")
    if result:
        print(f"✓ 完整下载成功")

        # 检查文件是否创建
        fee_file = os.path.join(output_dir, f"fund_{fund_code}_fee.json")
        overview_file = os.path.join(output_dir, f"fund_{fund_code}_overview.json")

        if os.path.exists(fee_file):
            print(f"✓ 费率文件已创建: {fee_file}")
        else:
            print(f"✗ 费率文件未创建")

        if os.path.exists(overview_file):
            print(f"✓ 概况文件已创建: {overview_file}")
        else:
            print(f"✗ 概况文件未创建")

        return True
    else:
        print("✗ 完整下载失败")
        return False


def test_parse_rate():
    """测试费率解析函数"""
    print("\n" + "="*60)
    print("测试5: 费率字符串解析")
    print("="*60)

    downloader = FundFeeDownloader("000001", "./test_data")

    test_cases = [
        ("1.20%", 0.012),
        ("0.12%", 0.0012),
        ("1.5%", 0.015),
        ("0.00", 0.0),
        ("-", None),
        ("--", None),
    ]

    all_passed = True
    for input_str, expected in test_cases:
        result = downloader._parse_rate(input_str)
        passed = result == expected
        all_passed = all_passed and passed

        status = "✓" if passed else "✗"
        print(f"{status} 解析 '{input_str}': 期望 {expected}, 得到 {result}")

    return all_passed


def test_multiple_funds():
    """测试多只基金下载"""
    print("\n" + "="*60)
    print("测试6: 批量下载多只基金")
    print("="*60)

    fund_codes = ["000001", "110022", "161725"]  # 几只常见的基金
    output_dir = "./test_data"

    success_count = 0
    for fund_code in fund_codes:
        print(f"\n下载基金 {fund_code}...")
        downloader = FundFeeDownloader(fund_code, output_dir)
        result = downloader.download(save=True)

        if result and result.get('基金名称'):
            print(f"  ✓ {fund_code}: {result.get('基金名称')}")
            success_count += 1
        else:
            print(f"  ✗ {fund_code}: 下载失败")

    print(f"\n批量下载结果: {success_count}/{len(fund_codes)} 只基金成功")
    return success_count == len(fund_codes)


def main():
    """运行所有测试"""
    print("="*60)
    print("基金费率下载器测试套件")
    print("="*60)

    # 创建测试目录
    os.makedirs("./test_data", exist_ok=True)

    # 运行测试
    tests = [
        ("费率下载功能", test_download_fee_info),
        ("JSON保存功能", test_save_to_json),
        ("基金概况下载", test_download_overview),
        ("完整下载流程", test_full_download),
        ("费率字符串解析", test_parse_rate),
        ("批量下载多只基金", test_multiple_funds),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n✗ 测试 '{test_name}' 发生异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status}: {test_name}")

    print(f"\n总计: {passed_count}/{total_count} 个测试通过")

    if passed_count == total_count:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  {total_count - passed_count} 个测试失败，请检查")


if __name__ == "__main__":
    main()
