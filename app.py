import time
import re
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--lang=vi")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)


def get_id(url):
    match = re.search(r'(?:v=|/reels?/|/videos/|v/|v=)(\d+)', url)
    return match.group(1) if match else None


def get_pseudo_content(driver, element, pseudo_type="before"):
    js = f"return window.getComputedStyle(arguments[0], '::{pseudo_type}').getPropertyValue('content');"
    content = driver.execute_script(js, element)
    if content and content not in ['none', 'normal']:
        return content.replace('"', '').replace("'", "").strip()
    return ""


def close_popups(driver):
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        driver.execute_script("""
            var closeBtn = document.querySelector('div[aria-label="Đóng"], div[aria-label="Close"], div[role="dialog"] div[role="button"]');
            if(closeBtn) closeBtn.click();
        """)
    except:
        pass


def scrape_single(driver, original_url, index, total):
    video_id = get_id(original_url)
    if not video_id:
        return {"url": original_url, "views": "N/A", "likes": "0", "comments": "0", "shares": "0", "error": "Invalid URL"}

    xpath_stats = "//span[contains(@class, 'x1lliihq') and contains(@class, 'x6ikm8r') and contains(@class, 'xuxw1ft')]"
    data = {"url": original_url, "video_id": video_id,
            "views": "N/A", "likes": "0", "comments": "0", "shares": "0"}

    try:
        watch_url = f"https://www.facebook.com/watch/?v={video_id}"
        driver.get(watch_url)
        time.sleep(6)
        close_popups(driver)
        try:
            view_el = driver.find_element(By.CLASS_NAME, "_26fq")
            data["views"] = view_el.text.strip()
        except:
            pass

        reel_url = f"https://www.facebook.com/reels/{video_id}/"
        driver.get(reel_url)
        time.sleep(6)
        close_popups(driver)

        stat_elements = driver.find_elements(By.XPATH, xpath_stats)
        temp_stats = []
        for el in stat_elements:
            v_real = el.text.strip()
            v_before = get_pseudo_content(driver, el, "before")
            v_after = get_pseudo_content(driver, el, "after")
            combined = (v_before + v_real + v_after).strip()
            if any(char.isdigit() for char in combined):
                temp_stats.append(combined)

        if len(temp_stats) >= 1:
            data["likes"] = temp_stats[0]
        if len(temp_stats) >= 2:
            data["comments"] = temp_stats[1]

        try:
            share_div = driver.find_element(
                By.XPATH, "//div[@aria-label='Chia sẻ' or @aria-label='Share']")
            share_text = share_div.text.strip()
            if not share_text:
                try:
                    share_text = share_div.find_element(
                        By.TAG_NAME, "span").text.strip()
                except:
                    pass
            data["shares"] = share_text if share_text else "0"
        except:
            data["shares"] = "0"

    except Exception as e:
        data["error"] = str(e)

    return data


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scrape", methods=["POST"])
def scrape():
    body = request.get_json()
    urls = [u.strip() for u in body.get("urls", []) if u.strip()]
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    def generate():
        driver = setup_driver()
        results = []
        try:
            for i, url in enumerate(urls):
                yield f"data: {json.dumps({'type': 'progress', 'index': i, 'total': len(urls), 'url': url})}\n\n"
                result = scrape_single(driver, url, i + 1, len(urls))
                results.append(result)
                yield f"data: {json.dumps({'type': 'result', 'data': result, 'index': i})}\n\n"
        finally:
            driver.quit()
            yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
