# import cloudscraper
import feedparser
import re
import requests
import io
import os
import ssl
import sys
from datetime import date, timedelta
from requests_html import HTMLSession
ssl._create_default_https_context = ssl._create_unverified_context
# tricks taken from https://stackoverflow.com/questions/50236117/scraping-ssl-certificate-verify-failed-error-for-http-en-wikipedia-org
import time

BROWSER_HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:105.0) Gecko/20100101 Firefox/105.0',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1'}

CROSSREF_HEADERS = {'User-Agent': 'networkspapers-bot/1.0 (+https://github.com/antoineallard/networkspapers)'}

timestr = time.strftime("%Y%m%d-%H%M%S")

log_file = open('logs/' + timestr + '.txt', 'w')
sys.stdout = log_file

if os.path.basename(os.getcwd()) != "code":
    os.chdir("code")

import rss2social


feeds = rss2social.rss2social()

# Loads files.
feeds.load_journals_data()
feeds.load_keywords()
feeds.load_already_seen_entries()
feeds.load_posts_to_review()

for journal in sorted(list(feeds.journals.keys())):

    entries = []
    # Reads the rss feed.
    print("Looking up " + feeds.journals[journal]["journal_abbrev"] + "...")

    if feeds.journals[journal]["reader"] == "feedparser":

        headers = dict(BROWSER_HEADERS)
        if feeds.journals[journal]["host"] != 'None':
            headers['Host'] = feeds.journals[journal]["host"]

        # Retries a few times with backoff: a single flaky/rate-limited
        # response should not be mistaken for "no new entries", and must
        # not crash the whole run (which would silently skip every journal
        # alphabetically after this one).
        entries = []
        for attempt in range(3):
            try:
                resp = requests.get(feeds.journals[journal]["feed2"], timeout=20.0,
                                     headers=headers if attempt > 0 else None)
            except requests.exceptions.RequestException as e:
                print("  - error reading RSS (attempt " + str(attempt + 1) + "): " + str(e) + "\n")
                time.sleep(2 ** attempt)
                continue

            # Put it to memory stream object universal feedparser
            content = io.BytesIO(resp.content)

            # Parse content
            feed = feedparser.parse(content)

            if len(feed.entries) > 0:
                entries = feed.entries
                break

            time.sleep(2 ** attempt)

    if feeds.journals[journal]["reader"] == "crossref":

        # Some publishers (e.g. Royal Society Publishing, Science/AAAS)
        # block plain RSS requests behind a JS bot challenge. Crossref's
        # REST API isn't bot-protected and lists recent works per journal.
        params = {
            "filter": "from-created-date:" + (date.today() - timedelta(days=30)).isoformat(),
            "sort": "created",
            "order": "desc",
            "rows": 100,
        }

        entries = []
        for attempt in range(3):
            try:
                resp = requests.get("https://api.crossref.org/journals/" + feeds.journals[journal]["issn"] + "/works",
                                     params=params, headers=CROSSREF_HEADERS, timeout=20.0)
                items = resp.json().get("message", {}).get("items", [])
            except (requests.exceptions.RequestException, ValueError) as e:
                print("  - error reading Crossref (attempt " + str(attempt + 1) + "): " + str(e) + "\n")
                time.sleep(2 ** attempt)
                continue

            if len(items) > 0:
                for item in items:
                    titles = item.get("title") or [""]
                    abstract = re.sub("<[^>]+>", "", item.get("abstract", "") or "")
                    entries.append({
                        "title": titles[0],
                        "summary": abstract,
                        "doi": item.get("DOI", ""),
                        "url": item.get("URL", ""),
                    })
                break

            time.sleep(2 ** attempt)


    if feeds.journals[journal]["reader"] == "HTMLSession":

        # https://practicaldatascience.co.uk/data-science/how-to-read-an-rss-feed-in-python
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:105.0) Gecko/20100101 Firefox/105.0',
                       'Accept-Language': 'en-US,en;q=0.5',
                       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                       'Connection': 'keep-alive',
                       'Accept-Encoding': 'gzip, deflate, br',
                       'Upgrade-Insecure-Requests': '1',
                       'Sec-Fetch-Dest': 'document',
                       'Sec-Fetch-Mode': 'navigate',
                       'Sec-Fetch-Site': 'none',
                       'Sec-Fetch-User': '?1'}
            session = HTMLSession()
            response = session.get(feeds.journals[journal]["feed2"], headers=headers)

            entries = []
            items = response.html.find("item", first=False)
            # print(items)
            for item in items:
                entry = {
                         feeds.journals[journal]["title"]:    item.find(feeds.journals[journal]["title"],    first=True).text,
                         feeds.journals[journal]["abstract"]: item.find(feeds.journals[journal]["abstract"], first=True).text,
                         feeds.journals[journal]["id"]:       item.find(feeds.journals[journal]["id"],       first=True).text,
                         feeds.journals[journal]["url"]:      item.find(feeds.journals[journal]["url"],      first=True).text
                        }

                entries.append(entry)

        except requests.exceptions.RequestException as e:
            print(e)

    # feed = feedparser.parse(feeds.journals[journal]["feed2"])
    print("  - found " + str(len(entries)) + " entries to filter")

    # Filters the entries.
    number_of_potential_entries = feeds.check_for_new_potential_entries(entries, journal)
    # number_of_potential_entries = 0
    # for entry in feed['entries']:

    #     # Title of the publication.
    #     entry_title = entry[feeds.journals[journal]["title"]]

    #     # Abstract of the publication.
    #     entry_abstract = ""
    #     if feeds.journals[journal]["abstract"] != "None":
    #         entry_abstract = entry[feeds.journals[journal]["abstract"]]

    #     # ID of the entry.
    #     entry_id = entry[feeds.journals[journal]["id"]]

    #     # Checks if this entry has already been seen.
    #     if entry_id not in feeds.already_seen_entries:

    #         # Checks if the title or abstract contains any sought keywords.
    #         info = entry_title + " " + entry_abstract
    #         info = re.findall(r'[\w]+|[.,;:!?%]', info)
    #         if (feeds.journals[journal]["whitelist"]) or any(word in info for word in feeds.keywords):

    #             # Link of the entry.
    #             entry_link = entry[feeds.journals[journal]["url"]]

    #             # Stores the tweet for future review.
    #             tweet = feeds.journals[journal]["journal_abbrev"] + ": " + entry_title + "\n" + entry_link
    #             feeds.posts_to_review.append(tweet)
    #             number_of_potential_entries += 1
    #             feeds.save_posts_to_review()

    #         # Keeps track of the entries that have already been seen.
    #         feeds.already_seen_entries.append(entry_id)
    #         feeds.save_already_seen_entries()

    if number_of_potential_entries > 0:
        print("  - found " + str(number_of_potential_entries) + " new potential relevant entries\n")
    else:
    #     print("  - found no new potential relevant entries\n")
        print("")

log_file.close()
