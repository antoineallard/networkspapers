import cloudscraper
import feedparser
import requests
import io
import logging
import os
import random
import re
import ssl
import sys
from requests_html import HTMLSession
ssl._create_default_https_context = ssl._create_unverified_context
# tricks taken from https://stackoverflow.com/questions/50236117/scraping-ssl-certificate-verify-failed-error-for-http-en-wikipedia-org
import time

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

    # Reads the rss feed.
    print("Looking up " + feeds.journals[journal]["journal_abbrev"] + "...")


    if feeds.journals[journal]["reader"] == "feedparser":
        # https://stackoverflow.com/questions/49087990/python-request-being-blocked-by-cloudflare
        #scraper = cloudscraper.create_scraper()
        scraper = cloudscraper.CloudScraper()
        try:
            file = scraper.get(feeds.journals[journal]["feed2"]).text
        except:
            # logger.warn("Timeout when reading RSS %s")
            print("Timeout when reading RSS\n")
            continue
        feed = feedparser.parse(file)
        entries = feed['entries']


        if len(feed.entries) == 0:
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
            if feeds.journals[journal]["host"] != 'None':
                headers['Host'] = feeds.journals[journal]["host"]

            # https://stackoverflow.com/questions/9772691/feedparser-with-timeout
            # https://stackoverflow.com/questions/19522990/catch-exception-and-continue-try-block-in-python
            try:
                resp = requests.get(feeds.journals[journal]["feed2"], timeout=random.randint(4, 8), headers=headers)
            except:
                # logger.warn("Timeout when reading RSS %s")
                print("Timeout when reading RSS\n")
                continue

            # Put it to memory stream object universal feedparser
            content = io.BytesIO(resp.content)
            # Parse content
            feed = feedparser.parse(content)
            entries = feed['entries']


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
