"""
note.com 記事データ収集スクリプト
対象: https://note.com/amiotsuka

使い方:
  # 依存インストール
  pip install playwright
  playwright install chromium

  # 実行
  python scrape_note.py
"""

import json
import csv
import time
import asyncio
from datetime import datetime

USERNAME = "amiotsuka"
BASE_URL = f"https://note.com/{USERNAME}"
API_URL = f"https://note.com/api/v2/creators/{USERNAME}/contents"
OUTPUT_JSON = "note_articles.json"
OUTPUT_CSV = "note_articles.csv"
REQUEST_INTERVAL = 1.5


def extract_article(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "key": item.get("key"),
        "title": item.get("name"),
        "type": item.get("type"),
        "status": item.get("status"),
        "published_at": item.get("publishAt"),
        "like_count": item.get("likeCount", 0),
        "comment_count": item.get("commentCount", 0),
        "price": item.get("price", 0),
        "is_paid": item.get("canRead") is False and item.get("price", 0) > 0,
        "url": f"https://note.com/{USERNAME}/n/{item.get('key')}",
        "eyecatch_url": item.get("eyecatch"),
        "description": item.get("description", ""),
    }


async def collect_with_playwright() -> list[dict]:
    from playwright.async_api import async_playwright

    articles = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ja-JP",
        )
        page = await context.new_page()

        # まずプロファイルページを開いてCookieを取得
        print(f"プロファイルページを読み込み中: {BASE_URL}")
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        page_num = 1
        print("記事データを収集中...")
        print("-" * 50)

        while True:
            url = f"{API_URL}?kind=note&page={page_num}"
            print(f"  ページ {page_num} を取得中...", end=" ", flush=True)

            response = await page.evaluate(f"""
                async () => {{
                    const res = await fetch("{url}", {{
                        headers: {{
                            "Accept": "application/json",
                            "X-Requested-With": "XMLHttpRequest"
                        }}
                    }});
                    if (!res.ok) return null;
                    return await res.json();
                }}
            """)

            if not response:
                print("取得失敗 — 終了")
                break

            contents = response.get("data", {}).get("contents", [])
            if not contents:
                print("データなし — 全ページ収集完了")
                break

            for item in contents:
                articles.append(extract_article(item))

            total_count = response.get("data", {}).get("totalCount", "?")
            print(f"{len(contents)} 件取得 (累計: {len(articles)}/{total_count})")

            is_last = response.get("data", {}).get("isLastPage", True)
            if is_last:
                print("  最終ページに到達")
                break

            page_num += 1
            await asyncio.sleep(REQUEST_INTERVAL)

        await browser.close()

    return articles


def save_json(articles: list[dict], path: str) -> None:
    output = {
        "scraped_at": datetime.now().isoformat(),
        "username": USERNAME,
        "total": len(articles),
        "articles": articles,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"JSON保存: {path}")


def save_csv(articles: list[dict], path: str) -> None:
    if not articles:
        return
    fields = list(articles[0].keys())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(articles)
    print(f"CSV保存: {path}")


def print_summary(articles: list[dict]) -> None:
    if not articles:
        print("記事が見つかりませんでした。")
        return

    total_likes = sum(a["like_count"] for a in articles)
    paid_count = sum(1 for a in articles if a["is_paid"])
    free_count = len(articles) - paid_count

    print("\n========== 収集結果サマリー ==========")
    print(f"総記事数      : {len(articles)} 件")
    print(f"無料記事      : {free_count} 件")
    print(f"有料記事      : {paid_count} 件")
    print(f"総いいね数    : {total_likes}")
    print(f"平均いいね数  : {total_likes / len(articles):.1f}")

    top5 = sorted(articles, key=lambda a: a["like_count"], reverse=True)[:5]
    print("\n--- いいね数 TOP5 ---")
    for i, a in enumerate(top5, 1):
        print(f"  {i}. [{a['like_count']:>4}♡] {a['title']}")
        print(f"       {a['url']}")
    print("=" * 38)


async def main():
    articles = await collect_with_playwright()
    if articles:
        save_json(articles, OUTPUT_JSON)
        save_csv(articles, OUTPUT_CSV)
    print_summary(articles)


if __name__ == "__main__":
    asyncio.run(main())
