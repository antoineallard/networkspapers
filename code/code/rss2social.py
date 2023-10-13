import json
import mastodon
import os
import re
import requests
import smtplib
import ssl
import tweepy

from datetime import datetime, timezone
from email.message import EmailMessage
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import List, Dict



class rss2social:

    def __init__(self,
                 journals_fname="../config/journals.json",
                 keywords_fname="../config/keywords.json",
                 already_seen_entries_fname="../data/already_seen_entries.json",
                 past_posts_fname="../data/past_posts.json",
                 future_posts_fname="../data/future_posts.json",
                 posts_to_review_fname="../data/posts_to_review.json",
                 bsky_cred="../config/bsky_cred.json",
                 twitter_cred="../config/twitter_cred.json",
                 mastodon_cred="../config/mastodon_cred.json",
                 googlegroup_cred="../config/googlegroup_cred.json",
                 slack_cred="../config/slack_dynamicalab_cred.json"):
        self.journals_fname = journals_fname
        self.keywords_fname = keywords_fname
        self.already_seen_entries_fname = already_seen_entries_fname
        self.future_posts_fname = future_posts_fname
        self.past_posts_fname = past_posts_fname
        self.posts_to_review_fname = posts_to_review_fname
        self.bsky_cred_fname = bsky_cred
        self.mastodon_cred_fname = mastodon_cred
        self.googlegroup_cred_fname = googlegroup_cred
        self.twitter_cred_fname = twitter_cred
        self.slack_cred_fname = slack_cred
        self.memory_length = int(75000)

    def check_for_new_potential_entries(self, entries, journal):
        number_of_potential_entries = 0
        for entry in entries:

            # Title of the publication.
            entry_title = entry[self.journals[journal]["title"]]

            if "replace_in_title" in self.journals[journal]:
                for word1, word2 in self.journals[journal]["replace_in_title"].items():
                    entry_title = entry_title.replace(word1, word2)

            # Abstract of the publication.
            entry_abstract = ""
            if self.journals[journal]["abstract"] != "None":
                entry_abstract = entry[self.journals[journal]["abstract"]]

            # ID of the entry.
            entry_id = entry[self.journals[journal]["id"]]

            # Checks if this entry has already been seen.
            if entry_id not in self.already_seen_entries:

                # Checks if the title or abstract contains any sought keywords.
                info = entry_title + " " + entry_abstract
                info = re.findall(r'[\w]+|[.,;:!?%]', info)
                if (self.journals[journal]["whitelist"]) or any(word in info for word in self.keywords):

                    # Link of the entry.
                    entry_link = entry[self.journals[journal]["url"]]

                    # Stores the tweet for future review.
                    tweet = self.journals[journal]["journal_abbrev"] + ": " + entry_title + "\n" + entry_link
                    self.posts_to_review.append(tweet)
                    number_of_potential_entries += 1
                    self.save_posts_to_review()

                # Keeps track of the entries that have already been seen.
                self.already_seen_entries.append(entry_id)
                self.save_already_seen_entries()

        return number_of_potential_entries

    def load_already_seen_entries(self):
        if os.path.isfile(self.already_seen_entries_fname):
            with open(self.already_seen_entries_fname, "r") as already_seen_entries_file:
                self.already_seen_entries = json.load(already_seen_entries_file)
                if len(self.already_seen_entries) > self.memory_length:
                    self.already_seen_entries = self.already_seen_entries[-self.memory_length:]
        else:
            self.already_seen_entries = []

    def load_future_posts(self):
        with open(self.future_posts_fname, "r") as future_posts_file:
            self.future_posts = json.load(future_posts_file)

    def load_journals_data(self):
        with open(self.journals_fname, "r") as journals_file:
            self.journals = json.load(journals_file)

    def load_keywords(self):
        with open(self.keywords_fname, "r") as keywords_file:
            self.keywords = json.load(keywords_file)

    def load_past_posts(self):
        with open(self.past_posts_fname, "r") as past_posts_file:
            self.past_posts = json.load(past_posts_file)

    def load_posts_to_review(self):
        if os.path.isfile(self.posts_to_review_fname):
            with open(self.posts_to_review_fname, "r") as posts_to_review_file:
                self.posts_to_review = json.load(posts_to_review_file)
        else:
            self.posts_to_review = []

    def load_bsky_cred(self):
        with open(self.bsky_cred_fname, "r") as bsky_cred_file:
            self.bsky_cred = json.load(bsky_cred_file)

    def load_googlegroup_cred(self):
        with open(self.googlegroup_cred_fname, "r") as googlegroup_cred_file:
            self.googlegroup_cred = json.load(googlegroup_cred_file)

    def load_mastodon_cred(self):
        with open(self.mastodon_cred_fname, "r") as mastodon_cred_file:
            self.mastodon_cred = json.load(mastodon_cred_file)

    def load_slack_cred(self):
        with open(self.slack_cred_fname, "r") as slack_cred_file:
            self.slack_cred = json.load(slack_cred_file)

    def load_twitter_cred(self):
        with open(self.twitter_cred_fname, "r") as twitter_cred_file:
            self.twitter_cred = json.load(twitter_cred_file)

    def post_to_bsky(self, text):

        # taken from https://atproto.com/blog/create-post

        resp = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": self.bsky_cred["handle"], "password": self.bsky_cred["app_password"]},
        )
        resp.raise_for_status()
        session = resp.json()

        def parse_urls(text: str) -> List[Dict]:
            spans = []
            # partial/naive URL regex based on: https://stackoverflow.com/a/3809435
            # tweaked to disallow some training punctuation
            url_regex = rb"[$|\W](https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*[-a-zA-Z0-9@%_\+~#//=])?)"
            text_bytes = text.encode("UTF-8")
            for m in re.finditer(url_regex, text_bytes):
                spans.append({
                    "start": m.start(1),
                    "end": m.end(1),
                    "url": m.group(1).decode("UTF-8"),
                })
            return spans

        # Parse facets from text and resolve the handles to DIDs
        def parse_facets(text: str) -> List[Dict]:
            facets = []
            for u in parse_urls(text):
                facets.append({
                    "index": {
                        "byteStart": u["start"],
                        "byteEnd": u["end"],
                    },
                    "features": [
                        {
                            "$type": "app.bsky.richtext.facet#link",
                            # NOTE: URI ("I") not URL ("L")
                            "uri": u["url"],
                        }
                    ],
                })
            return facets

        # Fetch the current time
        # Using a trailing "Z" is preferred over the "+00:00" format
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Required fields that each post must include
        post = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": now,
            "langs": ["en-US"],
        }
        post["facets"] = parse_facets(post["text"])

        resp = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": "Bearer " + session["accessJwt"]},
            json={
                "repo": session["did"],
                "collection": "app.bsky.feed.post",
                "record": post,
            },
        )
        resp.raise_for_status()

    def post_to_mastodon(self, toot):
        api = mastodon.Mastodon(
            access_token = self.mastodon_cred['access_token'],
            api_base_url = self.mastodon_cred['api_base_url']
        )
        api.toot(toot)

    def post_to_slack(self, tweet):
        client = WebClient(token=self.slack_cred['slack_bot_token'])
        try:
            response = client.chat_postMessage(channel=self.slack_cred['channel'], text=tweet)
        except SlackApiError as e:
            assert e.response["error"]

    def post_to_twitter(self, tweet):
        client = tweepy.Client(consumer_key=self.twitter_cred['consumer_key'], consumer_secret=self.twitter_cred['consumer_secret'],
                               access_token=self.twitter_cred['access_token'], access_token_secret=self.twitter_cred['access_token_secret'])
        response = client.create_tweet(text=tweet)
        print(f"https://twitter.com/user/status/{response.data['id']}")

    def post_to_googlegroup(self, email):
        # https://www.youtube.com/watch?v=g_j6ILT-X0k
        em = EmailMessage()
        em['From'] = self.googlegroup_cred['email_sender']
        em['To'] = self.googlegroup_cred['email_receiver']
        em['Subject'] = "New papers in Network Science - " + datetime.today().strftime('%Y/%m/%d')
        em.set_content(email)
        # Add SSL (layer of security)
        context = ssl.create_default_context()
        # Log in and send the email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(self.googlegroup_cred['email_sender'], self.googlegroup_cred['email_password'])
            smtp.sendmail(self.googlegroup_cred['email_sender'], self.googlegroup_cred['email_receiver'], em.as_string())

    def save_already_seen_entries(self):
        with open(self.already_seen_entries_fname, "w") as already_seen_entries_file:
            # json.dump(self.already_seen_entries, already_seen_entries_file)
            already_seen_entries_file.write(json.dumps(self.already_seen_entries, indent=4))

    def save_future_posts(self):
        # with open(self.future_posts_fname, "w") as future_posts_file:
        #     json.dump(self.future_posts, future_posts_file)
        with open(self.future_posts_fname, "w") as future_posts_file:
            future_posts_file.write(json.dumps(sorted(self.future_posts), indent=4))

    def save_past_posts(self):
        # with open(self.past_posts_fname, "w") as past_posts_file:
        #     json.dump(self.past_posts, past_posts_file)
        with open(self.past_posts_fname, "w") as past_posts_file:
            past_posts_file.write(json.dumps(self.past_posts, indent=4))

    def save_posts_to_review(self):
        with open(self.posts_to_review_fname, "w") as posts_to_review_file:
            posts_to_review_file.write(json.dumps(sorted(self.posts_to_review), indent=4))
            # json.dump(self.posts_to_review, posts_to_review_file)
