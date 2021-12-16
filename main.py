import requests
import os
import hashlib
import hmac
import time
import datetime

# Your Twitter bearer token (https://developer.twitter.com/en/portal/dashboard).
twitter_bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
# User id you want to check tweets for.
twitter_user_id = 44196397
# Can be anything.
twitter_user_agent = "twitter-binance-bot"

# Binance api key (https://www.binance.com/en/my/settings/api-management)
binance_api_key = os.environ.get("BINANCE_API_KEY")
# Binance api secret (https://www.binance.com/en/my/settings/api-management)
binance_api_secret = os.environ.get("BINANCE_API_SECRET")

# The trade pair you want to use
trade_pair = "DOGEUSDT"
# The quantity you want to trade in USDT
trade_amount = "45"
# The words that need to be tweeted in order to trigger a buy order
keywords = ["DOGE", "DOG", "DOGGY"]

timestamp = ""
last_tweet = ""
last_amount = 0


def bearer_oauth(auth):
    auth.headers["Authorization"] = f"Bearer {twitter_bearer_token}"
    auth.headers["User-Agent"] = twitter_user_agent
    return auth


def get_tweets():
    # The minimum of requesting tweets is 5, although we are only interested in the latest single tweet.
    response = requests.get(
        "https://api.twitter.com/2/users/{}/tweets?tweet.fields=created_at&exclude=replies&max_results=5".format(
            twitter_user_id), auth=bearer_oauth
    )
    if response.status_code != 200:
        raise Exception("Cannot get tweets (Code: {}) (Message: {})".format(response.status_code, response.text))
    return response.json()


def get_latest_tweet(json_data):
    all_tweets = json_data.get('data')
    latest_tweet = all_tweets[0]
    latest_tweet_text = latest_tweet.get('text').upper()
    print("latest tweet from user({}): {}".format(twitter_user_id, latest_tweet_text))
    return latest_tweet_text


def update_tweet_if_new(tweet):
    global last_tweet
    if tweet != last_tweet:
        last_tweet = tweet
        print("Latest tweet is new!")
        return True
    return False


def check_if_tweet_matches_keywords():
    for word in keywords:
        if word.upper() in last_tweet:
            print("{} matches criteria".format(word.upper()))
            return True
    return False


def set_new_timestamp():
    global timestamp
    data = requests.get("https://api.binance.com/api/v3/time").json()
    timestamp = data.get("serverTime")


def generate_binance_signature(side):
    return hmac.new(binance_api_secret.encode(),
                    "symbol={}&side={}&type=MARKET&quantity={}&timestamp={}".format(trade_pair,
                                                                                    side,
                                                                                    last_amount,
                                                                                    timestamp).encode(),
                    hashlib.sha256).hexdigest()


def create_order(side):
    set_new_timestamp()
    response = requests.post("https://api.binance.com/api/v3/order",
                             # add /test to the url to use the binance test network
                             params={
                                 "symbol": trade_pair,
                                 "side": side,
                                 "type": "MARKET",
                                 "quantity": last_amount,
                                 "timestamp": timestamp,
                                 "signature": generate_binance_signature(side),
                             },
                             headers={
                                 "X-MBX-APIKEY": binance_api_key,
                             })
    if response.status_code != 200:
        raise Exception(
            "Cannot make {} order (Code: {}) (Message: {})".format(side.lower(), response.status_code, response.text))
    return response


def create_buy_order():
    response = create_order("BUY")
    print("Buy order created for {} {}".format(last_amount, trade_pair))
    return response.json()


def create_sell_order():
    response = create_order("SELL")
    print("Sell order created for {} {}".format(last_amount, trade_pair))
    return response.json()


def calculate_trade_amount():
    global last_amount
    response = get_trade_value()
    price = response.json().get("price")
    amount = float(trade_amount) // float(price)
    amount = int(amount)
    print("Calculated amount for {} USDT: {} {}".format(trade_amount, amount, trade_pair))
    last_amount = amount
    return amount


def calculate_sell_value():
    response = get_trade_value()
    return last_amount * float(response.json().get("price"))


def get_trade_value():
    response = requests.get("https://api.binance.com/api/v3/ticker/price?symbol={}".format(trade_pair))
    if response.status_code != 200:
        raise Exception("Cannot get price (Code: {}) (Message: {})".format(response.status_code, response.text))
    return response


def main():
    global last_tweet
    last_tweet = get_latest_tweet(get_tweets())

    while True:
        try:
            time.sleep(45)
            print("datetime: " + str(datetime.datetime.now()))
            tweets_response = get_tweets()
            tweet = get_latest_tweet(tweets_response)
            if not update_tweet_if_new(tweet):
                continue
            if not check_if_tweet_matches_keywords():
                continue
            calculate_trade_amount()
            create_buy_order()
            time.sleep(300)  # wait 300 seconds before selling again, remove line if you don't want to sell
            create_sell_order()  # remove line if you don't want to sell
            print("Sell value: " + str(calculate_sell_value()))
        except Exception as e:
            print(e)
            continue


if __name__ == "__main__":
    main()
