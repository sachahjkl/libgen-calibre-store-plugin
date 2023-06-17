# -*- coding: utf-8 -*-
# License: GPLv3 Copyright: 2023, poochinski9
from __future__ import absolute_import, division, print_function, unicode_literals
import sys

import urllib.parse
import time

from bs4 import BeautifulSoup

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.web_store_dialog import WebStoreDialog

BASE_URL = "https://libgen.li"
USER_AGENT = "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko"

#####################################################################
# Plug-in base class
#####################################################################
def search_libgen(query, max_results=10, timeout=60):
    res = "25" if max_results <= 25 else "50" if max_results <= 50 else "100"
    search_url = f"{BASE_URL}/index.php?req={query.decode()}&res={res}"
    print("searching: " + search_url)
    print("max results: " + str(max_results))
    br = browser(user_agent=USER_AGENT)
    raw = br.open(search_url).read()
    soup = BeautifulSoup(raw, "html5lib")

    # Find the rows that represent each book, and skip the first item which is table headers
    trs = soup.select('table#tablelibgen > tbody > tr')

    print(len(trs))

    #map the trs to search results, filter out items that dont have a title or author, and limit it to max_results size
    output = [result for result in map(build_search_result, trs) if result.title and result.author][:max_results]
    return output

def build_search_result(tr):
    tds = tr.select('td')
    s = SearchResult()
    offset = int(tds[0]["colspan"] if tds[0].has_attr("colspan") else 1) - 1 

    s.title = str.format("{} - {}",tds[0].select_one('a').text.replace('\n', '').strip(), tds[0].select_one('font').text.replace('\n', '').strip() )
    s.author =  (tds[1 - offset].text if tds[1].text else "N/A") if 1 - offset >= 0 else "N/A"
    s.detail_item = BASE_URL + "/" + tds[0 - offset].select_one("a:first-of-type").get("href") if 0 - offset >= 0 else "N/A"
    year = tds[3 - offset].text if 3 - offset >= 0 else "N/A"
    pages = tds[5 - offset].text if 5 - offset >= 0 else "N/A"
    size = tds[6 - offset].text if 6 - offset >= 0 else "N/A"
    s.price = f"{size}\n{pages} pages\n{year}"  # use price column to display more size, pages, year
    s.formats = tds[7 - offset].text.upper() if 7 - offset >= 0 else "N/A"
    s.drm = SearchResult.DRM_UNLOCKED
    s.mirror1_url = tds[8 - offset].select_one("a:first-of-type").get("href") if 8 - offset >= 0 else "N/A"

    if s.mirror1_url[0] == "/":
        s.mirror1_url = BASE_URL + s.mirror1_url

    return s


class LibgenStorePlugin(BasicStoreConfig, StorePlugin):
    def open(self, parent=None, detail_item=None, external=False):
        url = BASE_URL

        if external or self.config.get("open_external", False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get("tags", ""))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        for result in search_libgen(query, max_results=max_results, timeout=timeout):
            yield result

    def get_details(self, search_result, timeout):
        s = search_result
        br = browser(user_agent=USER_AGENT)
        while True:
            try:
                raw = br.open(s.mirror1_url).read()
                break
            except:
                # sever error, retry after delay
                time.sleep(0.1)

        soup2 = BeautifulSoup(raw, "html5lib")
        download_a = soup2.select('div[id="download"] > ul > li > a')[0]
        download_url = download_a.get("href")

        new_base_url = urllib.parse.urlparse(s.mirror1_url).hostname
        image_url = "http://" + new_base_url + soup2.select("img")[0].get("src")

        s.downloads[s.formats] = download_url
        s.cover_url = image_url

if __name__ == "__main__":
    for result in search_libgen(bytes(" ".join(sys.argv[1:]), "utf-8")):
        print(result)
