from distutils.util import strtobool
import webbrowser
import random
import os

if os.path.basename(os.getcwd()) != "code":
    os.chdir("code")

import rss2social


def prompt(query, if_empty):
    val = input(query)
    if val == "":
        return if_empty
    try:
        ret = strtobool(val)
    except ValueError:
        if val in ['q', 'Q', 'quit', 'Quit', 'QUIT']:
            quit()
        else:
            return prompt(query, if_empty)
    return ret


feeds = rss2social.rss2social()

feeds.load_future_posts()
# feeds.load_past_posts()
feeds.load_posts_to_review()
# feeds.load_mastodon_cred()
# feeds.load_twitter_cred()

# Shuffles the list.
random.shuffle(feeds.posts_to_review)

# Loops over all entries.
nb_entries = len(feeds.posts_to_review)
for i in range(nb_entries-1, -1, -1):

    # Review the tweet.
    print("\n\n\nPotential tweet {} out of {}:\n".format(nb_entries-i, nb_entries))
    print(feeds.posts_to_review[i], end="\n\n")

    # if prompt(query="Quit? [y/N]", if_empty=False):
    #     quit()

    if prompt(query="Open in browser? [Y/n/q]", if_empty=True):
        webbrowser.get('Safari').open(feeds.posts_to_review[i].split("\n")[-1])

    if prompt(query="Save tweet/toot? [Y/n/q]", if_empty=True):
        # feeds.post_to_twitter(feeds.posts_to_review[i])
        # feeds.post_to_mastodon(feeds.posts_to_review[i])
        # # feeds.post_to_ryver(feeds.posts_to_review[i])
        # feeds.past_posts.append(feeds.posts_to_review[i])
        feeds.future_posts.append(feeds.posts_to_review[i])
        print("Tweet/toot saved.")

    # Removes the tweet from the list.
    feeds.posts_to_review.pop(i)
    # feeds.save_past_posts()
    feeds.save_future_posts()
    feeds.save_posts_to_review()