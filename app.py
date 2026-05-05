import streamlit as st
import streamlit.components.v1 as components
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# --- CẤU HÌNH SELENIUM ---


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    # Sử dụng WebDriver Manager để tự động tải Driver và Chrome
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver


def get_id(url):
    match = re.search(r'(?:v=|/reels?/|/videos/|v/|v=)(\d+)', url)
    return match.group(1) if match else None


def get_pseudo_content(driver, element, pseudo_type="before"):
    js = f"return window.getComputedStyle(arguments[0], '::{pseudo_type}').getPropertyValue('content');"
    content = driver.execute_script(js, element)
    return content.replace('"', '').replace("'", "").strip() if content and content not in ['none', 'normal'] else ""


def scrape_single(driver, url):
    video_id = get_id(url)
    if not video_id:
        return None

    data = {"url": url, "video_id": video_id, "views": "N/A",
            "likes": "0", "comments": "0", "shares": "0"}
    try:
        # Lấy View
        driver.get(f"https://www.facebook.com/watch/?v={video_id}")
        time.sleep(5)
        try:
            data["views"] = driver.find_element(
                By.CLASS_NAME, "_26fq").text.strip()
        except:
            pass

        # Lấy Tương tác
        driver.get(f"https://www.facebook.com/reels/{video_id}/")
        time.sleep(5)

        xpath_stats = "//span[contains(@class, 'x1lliihq') and contains(@class, 'x6ikm8r') and contains(@class, 'xuxw1ft')]"
        stats = []
        for el in driver.find_elements(By.XPATH, xpath_stats):
            combined = (get_pseudo_content(driver, el, "before") +
                        el.text + get_pseudo_content(driver, el, "after")).strip()
            if any(c.isdigit() for c in combined):
                stats.append(combined)

        if len(stats) >= 1:
            data["likes"] = stats[0]
        if len(stats) >= 2:
            data["comments"] = stats[1]

        try:
            share_div = driver.find_element(
                By.XPATH, "//div[@aria-label='Chia sẻ' or @aria-label='Share']")
            data["shares"] = share_div.text.strip() or share_div.find_element(
                By.TAG_NAME, "span").text.strip()
        except:
            pass
    except:
        pass
    return data


# --- GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="FB Scraper Pro", layout="wide")

# Nhúng CSS/HTML của bạn (Bản rút gọn để tương tác với Streamlit)
st.markdown(f"""
    <style>
    /* Dán toàn bộ phần <style> của bạn vào đây */
    body {{ background: #0e1117; color: white; }}
    /* ... (Giữ nguyên CSS Cyberpunk của bạn) ... */
    </style>
    """, unsafe_allow_html=True)

st.title("⚡ Facebook Reel Stats Tracker")
urls_input = st.text_area("🔗 Dán danh sách URL (mỗi dòng 1 link):", height=200)

if st.button("Bắt đầu Scrape"):
    urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
    if urls:
        results_container = st.container()
        driver = setup_driver()
        all_data = []

        with st.status("🚀 Đang tiến hành cào dữ liệu...", expanded=True) as status:
            for i, url in enumerate(urls):
                st.write(f"🔍 Đang xử lý: {url}")
                res = scrape_single(driver, url)
                if res:
                    all_data.append(res)
            driver.quit()
            status.update(label="✅ Hoàn thành!",
                          state="complete", expanded=False)

        # Hiển thị bảng kết quả đẹp
        st.subheader("📊 Kết quả")
        st.table(all_data)

        # Nút Export
        csv = "Video ID,Views,Likes,Comments,Shares,URL\n"
        for r in all_data:
            csv += f"{r['video_id']},{r['views']},{r['likes']},{r['comments']},{r['shares']},{r['url']}\n"
        st.download_button("⬇️ Tải về CSV", csv, "results.csv", "text/csv")
