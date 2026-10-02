#!/usr/bin/env python3
"""daily_motivation.py | the 7 AM Punjabi motivation post on Telegram.

Runs every morning from .github/workflows/daily-motivation.yml. Each day it
picks one motivational message and one House of Aspirants feature to promote
(daily challenge, expected MCQs, mock tests, notes, current affairs, Rank 2
blueprint), so students get a reason to open the site with their morning.

The pick is driven by the date, so the same day always gives the same post
(a re-run never posts something different) and consecutive days never repeat:
the message list and the promo list have different lengths, so the pairs keep
changing for months.

    python3 scripts/daily_motivation.py            # post today's message
    python3 scripts/daily_motivation.py --dry-run  # print it only
    python3 scripts/daily_motivation.py --date 2026-10-05 --dry-run

Uses the same TELEGRAM_BOT_TOKEN secret and TELEGRAM_CHANNEL variable as the
upload notifications. Standard library only.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://houseofaspirants.in"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# (headline, body) - original lines written for Punjab exam aspirants.
MESSAGES = [
    ("ਅੱਜ ਦੀ ਮਿਹਨਤ, ਕੱਲ੍ਹ ਦੀ ਵਰਦੀ 👮",
     "ਜਿਹੜੀ ਵਰਦੀ ਦਾ ਸੁਪਨਾ ਤੁਸੀਂ ਦੇਖਦੇ ਹੋ, ਉਹ ਕਿਸੇ ਇੱਕ ਦਿਨ ਨਹੀਂ ਮਿਲਦੀ - ਉਹ ਰੋਜ਼ ਦੇ ਛੋਟੇ-ਛੋਟੇ ਘੰਟਿਆਂ ਨਾਲ ਬਣਦੀ ਹੈ। ਅੱਜ ਦਾ ਘੰਟਾ ਨਾ ਗਵਾਓ।"),
    ("ਮੁਕਾਬਲਾ ਦੂਜਿਆਂ ਨਾਲ ਨਹੀਂ, ਕੱਲ੍ਹ ਵਾਲੇ ਆਪਣੇ-ਆਪ ਨਾਲ ਹੈ 💪",
     "ਕੱਲ੍ਹ ਨਾਲੋਂ ਅੱਜ 5 ਸਵਾਲ ਵੱਧ ਸਹੀ ਕਰ ਲਏ, ਤਾਂ ਤੁਸੀਂ ਜਿੱਤ ਰਹੇ ਹੋ। Merit list ਉਹਨਾਂ ਦੀ ਬਣਦੀ ਹੈ ਜੋ ਰੋਜ਼ ਥੋੜ੍ਹਾ ਅੱਗੇ ਵਧਦੇ ਨੇ।"),
    ("ਥੱਕ ਗਏ ਹੋ? ਰੁਕੋ ਨਾ, ਸਾਹ ਲਓ ਤੇ ਫਿਰ ਤੁਰੋ 🌅",
     "ਤਿਆਰੀ ਵਿੱਚ ਥਕਾਵਟ ਆਉਣੀ ਕੁਦਰਤੀ ਹੈ। ਹਾਰ ਉਦੋਂ ਹੁੰਦੀ ਹੈ ਜਦੋਂ ਅਸੀਂ ਤੁਰਨਾ ਛੱਡ ਦਿੰਦੇ ਹਾਂ। ਅੱਜ ਹੌਲੀ ਚੱਲੋ, ਪਰ ਚੱਲੋ ਜ਼ਰੂਰ।"),
    ("ਇੱਕ ਨੰਬਰ ਦੀ ਕੀਮਤ ਪੁੱਛੋ ਉਸ ਤੋਂ, ਜੋ ਇੱਕ ਨੰਬਰ ਨਾਲ ਰਹਿ ਗਿਆ 🎯",
     "Punjab ਦੇ ਪੇਪਰਾਂ ਵਿੱਚ ਹਜ਼ਾਰਾਂ ਬੱਚੇ 0.5 ਨੰਬਰ ਦੇ ਫ਼ਰਕ ਨਾਲ ਪਿੱਛੇ ਰਹਿ ਜਾਂਦੇ ਨੇ। ਅੱਜ ਦੀ practice ਉਹੀ ਅੱਧਾ ਨੰਬਰ ਹੈ।"),
    ("ਸਿਲੇਬਸ ਵੱਡਾ ਹੈ, ਪਰ ਤੁਹਾਡਾ ਇਰਾਦਾ ਉਸ ਤੋਂ ਵੀ ਵੱਡਾ ਹੈ 🔥",
     "ਪੂਰਾ ਸਿਲੇਬਸ ਇੱਕ ਦਿਨ ਵਿੱਚ ਨਹੀਂ ਮੁੱਕਦਾ। ਅੱਜ ਸਿਰਫ਼ ਇੱਕ topic ਪੱਕਾ ਕਰੋ - 30 ਦਿਨਾਂ ਵਿੱਚ 30 topics ਤੁਹਾਡੇ ਹੋਣਗੇ।"),
    ("ਮੋਬਾਈਲ ਤੁਹਾਡਾ ਸਮਾਂ ਖਾ ਰਿਹਾ ਹੈ ਜਾਂ ਤੁਹਾਡੀ ਤਿਆਰੀ ਕਰਵਾ ਰਿਹਾ ਹੈ? 📱",
     "ਉਹੀ ਫ਼ੋਨ reels ਵਿੱਚ 2 ਘੰਟੇ ਲੈ ਜਾਂਦਾ ਹੈ, ਅਤੇ ਉਹੀ ਫ਼ੋਨ 20 ਮਿੰਟ ਵਿੱਚ ਇੱਕ ਪੂਰਾ ਟੈਸਟ ਵੀ ਕਰਵਾ ਦਿੰਦਾ ਹੈ। ਫ਼ੈਸਲਾ ਤੁਹਾਡਾ।"),
    ("ਲੋਕ ਨਤੀਜਾ ਦੇਖਦੇ ਨੇ, ਤਿਆਰੀ ਕੋਈ ਨਹੀਂ ਦੇਖਦਾ 🌙",
     "ਰਾਤਾਂ ਨੂੰ ਪੜ੍ਹੇ ਘੰਟੇ ਕਿਸੇ ਨੂੰ ਨਹੀਂ ਦਿਸਦੇ, ਪਰ ਜਿਸ ਦਿਨ ਨਾਮ merit list ਵਿੱਚ ਆਉਂਦਾ ਹੈ, ਸਾਰਾ ਪਿੰਡ ਦੇਖਦਾ ਹੈ। ਲੱਗੇ ਰਹੋ।"),
    ("ਗ਼ਲਤੀ ਤੋਂ ਨਾ ਡਰੋ, ਗ਼ਲਤੀ ਦੁਹਰਾਉਣ ਤੋਂ ਡਰੋ ✍️",
     "Practice ਵਿੱਚ ਕੀਤੀ ਹਰ ਗ਼ਲਤੀ ਪੇਪਰ ਵਿੱਚ ਇੱਕ ਨੰਬਰ ਬਚਾਉਂਦੀ ਹੈ। ਗ਼ਲਤ ਸਵਾਲਾਂ ਦੀ explanation ਜ਼ਰੂਰ ਪੜ੍ਹੋ।"),
    ("ਮਾਂ-ਪਿਓ ਦੇ ਚਿਹਰੇ ਦੀ ਮੁਸਕਾਨ ਯਾਦ ਕਰੋ 🙏",
     "ਜਿਸ ਦਿਨ joining letter ਘਰ ਆਵੇਗਾ, ਉਸ ਦਿਨ ਦੀ ਖ਼ੁਸ਼ੀ ਅੱਜ ਦੀ ਹਰ ਮੁਸ਼ਕਲ ਤੋਂ ਵੱਡੀ ਹੋਵੇਗੀ। ਉਸ ਦਿਨ ਲਈ ਅੱਜ ਪੜ੍ਹੋ।"),
    ("ਹਰ topper ਕਦੇ beginner ਸੀ 🌱",
     "ਜਿਨ੍ਹਾਂ ਨੂੰ ਤੁਸੀਂ ਅੱਜ selected ਦੇਖਦੇ ਹੋ, ਉਹ ਵੀ ਕਦੇ ਪਹਿਲੇ ਟੈਸਟ ਵਿੱਚ 8/25 ਲੈ ਕੇ ਆਏ ਸੀ। ਸ਼ੁਰੂਆਤ ਛੋਟੀ ਹੋ ਸਕਦੀ ਹੈ, ਮੰਜ਼ਿਲ ਨਹੀਂ।"),
    ("ਪੜ੍ਹਿਆ ਹੋਇਆ ਤਾਂ ਹੀ ਕੰਮ ਆਉਂਦਾ ਹੈ ਜੇ ਯਾਦ ਰਹੇ 🧠",
     "ਸਿਰਫ਼ ਪੜ੍ਹਨ ਨਾਲ ਨਹੀਂ, ਦੁਹਰਾਉਣ ਨਾਲ ਯਾਦ ਪੱਕੀ ਹੁੰਦੀ ਹੈ। ਅੱਜ ਪਿਛਲੇ ਹਫ਼ਤੇ ਵਾਲਾ topic ਇੱਕ ਵਾਰ ਫਿਰ ਟੈਸਟ ਕਰੋ।"),
    ("ਹਾਲਾਤ ਬਹਾਨਾ ਨਹੀਂ, ਹੌਸਲਾ ਬਣਨੇ ਚਾਹੀਦੇ ਨੇ 💯",
     "ਪਿੰਡਾਂ ਦੇ ਕਈ ਬੱਚੇ ਖੇਤਾਂ ਵਿੱਚ ਕੰਮ ਕਰਕੇ ਵੀ select ਹੋਏ ਨੇ। ਸਹੂਲਤਾਂ ਘੱਟ ਹੋ ਸਕਦੀਆਂ ਨੇ, ਇਰਾਦਾ ਘੱਟ ਨਹੀਂ ਹੋਣਾ ਚਾਹੀਦਾ।"),
    ("ਸਵੇਰ ਦਾ ਪਹਿਲਾ ਘੰਟਾ ਦਿਨ ਦੀ ਦਿਸ਼ਾ ਤੈਅ ਕਰਦਾ ਹੈ ☀️",
     "ਉੱਠਦੇ ਹੀ ਫ਼ੋਨ 'ਤੇ ਖ਼ਬਰਾਂ ਨਹੀਂ - ਪਹਿਲਾਂ 20 ਸਵਾਲ। ਦਿਨ ਦੀ ਸ਼ੁਰੂਆਤ ਜਿੱਤ ਨਾਲ ਕਰੋ।"),
    ("ਕਿਸਮਤ ਵੀ ਉਹਨਾਂ ਦਾ ਸਾਥ ਦਿੰਦੀ ਹੈ ਜੋ ਮਿਹਨਤ ਨਹੀਂ ਛੱਡਦੇ 🍀",
     "ਪੇਪਰ ਵਾਲੇ ਦਿਨ 'luck' ਉਸੇ ਦਾ ਚੱਲਦਾ ਹੈ ਜਿਸ ਨੇ ਉਹ ਸਵਾਲ ਪਹਿਲਾਂ practice ਵਿੱਚ ਦੇਖਿਆ ਹੋਵੇ।"),
    ("ਤੁਹਾਡੀ ਚੁੱਪ ਮਿਹਨਤ ਇੱਕ ਦਿਨ ਸ਼ੋਰ ਮਚਾਏਗੀ 📢",
     "ਲੋਕਾਂ ਦੀਆਂ ਗੱਲਾਂ ਦਾ ਜਵਾਬ ਬਹਿਸ ਨਾਲ ਨਹੀਂ, result ਨਾਲ ਦਿਓ। ਅੱਜ ਦਾ ਕੰਮ ਅੱਜ ਪੂਰਾ ਕਰੋ।"),
    ("Reasoning ਔਖੀ ਨਹੀਂ, ਬਸ practice ਮੰਗਦੀ ਹੈ 🧩",
     "ਜਿਹੜਾ ਪ੍ਰਸ਼ਨ ਅੱਜ 2 ਮਿੰਟ ਲੈਂਦਾ ਹੈ, 10 ਦਿਨ practice ਤੋਂ ਬਾਅਦ 30 ਸਕਿੰਟ ਲਵੇਗਾ। ਰਫ਼ਤਾਰ ਰੋਜ਼ ਬਣਦੀ ਹੈ।"),
    ("ਹਾਰ ਮੰਨਣ ਤੋਂ ਪਹਿਲਾਂ ਸੋਚੋ, ਤੁਸੀਂ ਸ਼ੁਰੂ ਕਿਉਂ ਕੀਤਾ ਸੀ 🔁",
     "ਜਿਸ ਕਾਰਨ ਤੁਸੀਂ ਤਿਆਰੀ ਸ਼ੁਰੂ ਕੀਤੀ ਸੀ, ਉਹ ਕਾਰਨ ਅੱਜ ਵੀ ਓਨਾ ਹੀ ਵੱਡਾ ਹੈ। ਬਸ ਇੱਕ ਦਿਨ ਹੋਰ - ਰੋਜ਼।"),
    ("Punjab GK ਪੰਜਾਬੀ ਹੋਣ ਦਾ ਮਾਣ ਵੀ ਹੈ ਅਤੇ ਪੱਕੇ ਨੰਬਰ ਵੀ 🌾",
     "ਆਪਣੇ ਪੰਜਾਬ ਦਾ ਇਤਿਹਾਸ, ਗੁਰੂ ਸਾਹਿਬਾਨ, ਦਰਿਆ, ਲੋਕ-ਨਾਚ - ਇਹ ਸਵਾਲ ਹਰ ਪੇਪਰ ਵਿੱਚ ਆਉਂਦੇ ਨੇ। ਇਹਨਾਂ ਨੂੰ ਗੁਆਉਣਾ ਨਹੀਂ।"),
    ("ਇੱਕ ਸਾਲ ਦੀ ਪੂਰੀ ਮਿਹਨਤ, ਸਾਰੀ ਉਮਰ ਦਾ ਆਰਾਮ 🏡",
     "ਅੱਜ ਦੀ ਥੋੜ੍ਹੀ ਕੁਰਬਾਨੀ - ਘੱਟ ਘੁੰਮਣਾ, ਘੱਟ ਫ਼ੋਨ - ਕੱਲ੍ਹ ਪੱਕੀ ਸਰਕਾਰੀ ਨੌਕਰੀ ਬਣ ਸਕਦੀ ਹੈ।"),
    ("Consistency ਹੀ ਅਸਲ talent ਹੈ ⏳",
     "ਰੋਜ਼ 2 ਘੰਟੇ ਪੜ੍ਹਨ ਵਾਲਾ, ਹਫ਼ਤੇ ਵਿੱਚ ਇੱਕ ਦਿਨ 12 ਘੰਟੇ ਪੜ੍ਹਨ ਵਾਲੇ ਤੋਂ ਅੱਗੇ ਨਿਕਲ ਜਾਂਦਾ ਹੈ। ਰੋਜ਼ਾਨਾ ਦੀ ਆਦਤ ਬਣਾਓ।"),
    ("ਡਰ ਨੂੰ ਤਿਆਰੀ ਨਾਲ ਹਰਾਓ 🛡️",
     "ਪੇਪਰ ਦਾ ਡਰ ਉਦੋਂ ਹੀ ਮੁੱਕਦਾ ਹੈ ਜਦੋਂ ਤੁਸੀਂ ਘਰ ਬੈਠੇ timer ਲਾ ਕੇ ਪੇਪਰ ਵਰਗੇ ਟੈਸਟ ਦਿੰਦੇ ਹੋ। Exam hall ਨੂੰ ਆਪਣਾ ਕਮਰਾ ਬਣਾ ਲਓ।"),
    ("ਹਰ ਦਿਨ ਇੱਕ ਨਵਾਂ ਮੌਕਾ ਹੈ 🌄",
     "ਕੱਲ੍ਹ ਪੜ੍ਹਾਈ ਨਹੀਂ ਹੋਈ? ਕੋਈ ਗੱਲ ਨਹੀਂ। ਕੱਲ੍ਹ ਬੀਤ ਗਿਆ, ਅੱਜ ਤੁਹਾਡੇ ਹੱਥ ਵਿੱਚ ਹੈ। ਹੁਣੇ ਸ਼ੁਰੂ ਕਰੋ।"),
    ("ਸਮਾਂ ਸਭ ਨੂੰ 24 ਘੰਟੇ ਹੀ ਮਿਲਦਾ ਹੈ ⌛",
     "ਫ਼ਰਕ ਸਿਰਫ਼ ਇਹ ਹੈ ਕਿ ਕੌਣ ਉਹਨਾਂ ਨੂੰ ਕਿੱਥੇ ਲਾਉਂਦਾ ਹੈ। ਅੱਜ ਆਪਣੇ 24 ਘੰਟਿਆਂ ਵਿੱਚੋਂ ਘੱਟੋ-ਘੱਟ 4 ਆਪਣੇ ਸੁਪਨੇ ਨੂੰ ਦਿਓ।"),
    ("Current Affairs ਰੋਜ਼ ਦਾ ਖਾਣਾ ਹੈ, ਇੱਕ ਦਿਨ ਦਾ ਲੰਗਰ ਨਹੀਂ 🗞️",
     "ਪੇਪਰ ਤੋਂ ਇੱਕ ਹਫ਼ਤਾ ਪਹਿਲਾਂ 6 ਮਹੀਨਿਆਂ ਦੇ Current Affairs ਨਹੀਂ ਪੜ੍ਹੇ ਜਾਂਦੇ। ਰੋਜ਼ 15 ਮਿੰਟ ਦਿਓ।"),
    ("ਤੁਸੀਂ ਜਿੰਨਾ ਸੋਚਦੇ ਹੋ, ਉਸ ਤੋਂ ਵੱਧ ਕਾਬਲ ਹੋ ✨",
     "ਆਪਣੇ ਆਪ 'ਤੇ ਸ਼ੱਕ ਕਰਨਾ ਛੱਡੋ। ਜੋ ਸਵਾਲ ਅੱਜ ਔਖੇ ਲੱਗਦੇ ਨੇ, ਉਹ ਕੁਝ ਹਫ਼ਤਿਆਂ ਵਿੱਚ ਆਸਾਨ ਲੱਗਣਗੇ।"),
    ("ਪੱਕਾ ਇਰਾਦਾ + ਸਹੀ ਦਿਸ਼ਾ = Selection 🧭",
     "ਮਿਹਨਤ ਤਾਂ ਸਾਰੇ ਕਰਦੇ ਨੇ; ਜਿੱਤਦਾ ਉਹ ਹੈ ਜੋ ਸਹੀ ਚੀਜ਼ ਪੜ੍ਹਦਾ ਹੈ। ਪੇਪਰ ਦੇ pattern ਮੁਤਾਬਕ ਤਿਆਰੀ ਕਰੋ।"),
    ("ਆਰਾਮ ਕਰੋ, ਪਰ ਹਾਰ ਨਾ ਮੰਨੋ 😌",
     "ਦਿਮਾਗ਼ ਨੂੰ ਆਰਾਮ ਵੀ ਚਾਹੀਦਾ ਹੈ - ਚੰਗੀ ਨੀਂਦ, ਥੋੜ੍ਹੀ ਕਸਰਤ। ਤੰਦਰੁਸਤ ਸਰੀਰ ਵਿੱਚ ਹੀ ਤੇਜ਼ ਦਿਮਾਗ਼ ਹੁੰਦਾ ਹੈ।"),
    ("Mock test ਤੋਂ ਭੱਜੋ ਨਾ, ਉਹ ਤੁਹਾਡਾ ਸ਼ੀਸ਼ਾ ਹੈ 🪞",
     "Mock ਵਿੱਚ ਘੱਟ ਨੰਬਰ ਬੁਰੇ ਨਹੀਂ - ਉਹ ਦੱਸਦੇ ਨੇ ਕਿ ਕਿੱਥੇ ਮਿਹਨਤ ਕਰਨੀ ਹੈ। ਅਸਲ ਪੇਪਰ ਵਿੱਚ ਘੱਟ ਨੰਬਰ ਬੁਰੇ ਹੁੰਦੇ ਨੇ।"),
    ("ਸੁਪਨਾ ਵੱਡਾ ਰੱਖੋ, ਕਦਮ ਛੋਟੇ ਪਰ ਪੱਕੇ 👣",
     "Inspector ਬਣਨਾ ਹੈ? ਅੱਜ ਸਿਰਫ਼ ਇੱਕ ਟੈਸਟ, ਇੱਕ chapter, ਇੱਕ revision। ਛੋਟੇ ਕਦਮ ਹੀ ਲੰਬਾ ਸਫ਼ਰ ਤੈਅ ਕਰਦੇ ਨੇ।"),
    ("ਜਿਹੜੇ ਅੱਜ ਹੱਸਦੇ ਨੇ, ਕੱਲ੍ਹ ਉਹੀ ਮਿਸਾਲ ਦੇਣਗੇ 🏆",
     "ਲੋਕਾਂ ਦੀਆਂ ਗੱਲਾਂ ਨੂੰ ਆਪਣੀ ਤਾਕਤ ਬਣਾਓ। Selection ਤੋਂ ਬਾਅਦ ਸਭ ਤੋਂ ਪਹਿਲਾਂ ਵਧਾਈ ਵੀ ਉਹੀ ਦੇਣਗੇ।"),
    ("ਘੱਟ ਪੜ੍ਹੋ, ਪਰ ਪੱਕਾ ਪੜ੍ਹੋ 📌",
     "10 ਕਿਤਾਬਾਂ ਅੱਧੀਆਂ ਪੜ੍ਹਨ ਨਾਲੋਂ 1 ਕਿਤਾਬ 3 ਵਾਰ ਪੜ੍ਹਨੀ ਬਿਹਤਰ ਹੈ। Quality > Quantity।"),
    ("ਰੱਬ 'ਤੇ ਭਰੋਸਾ, ਆਪਣੀ ਮਿਹਨਤ 'ਤੇ ਯਕੀਨ 🙌",
     "ਅਰਦਾਸ ਕਰੋ, ਪਰ ਕਿਤਾਬ ਬੰਦ ਨਾ ਕਰੋ। ਕਿਰਤ ਕਰਨਾ ਸਾਡੇ ਪੰਜਾਬ ਦੀ ਪਛਾਣ ਹੈ।"),
]

# (headline, body, path) - what to open today. Lengths differ from MESSAGES
# on purpose, so the pairing keeps changing.
PROMOS = [
    ("🎯 ਅੱਜ ਦਾ Daily Challenge ਤਿਆਰ ਹੈ",
     "ਹਰ ਰੋਜ਼ ਨਵੇਂ mixed MCQs - ਪੰਜਾਬੀ ਅਤੇ English ਦੋਵਾਂ ਵਿੱਚ, ਹਰ ਜਵਾਬ ਦੀ ਵਿਆਖਿਆ ਨਾਲ।",
     "/quiz?mode=daily"),
    ("🧠 Expected MCQs - ਪੇਪਰ ਵਰਗੇ ਸਵਾਲ",
     "Punjab Police, PSSSB, Patwari ਦੇ pattern 'ਤੇ ਬਣੇ topic-wise sets। ਟਾਈਮਰ ਨਾਲ practice ਕਰੋ।",
     "/expected-mcqs"),
    ("📝 Full Mock Test ਦਿਓ",
     "ਪੇਪਰ ਤੋਂ ਪਹਿਲਾਂ ਆਪਣੀ ਅਸਲ ਤਿਆਰੀ ਮਾਪੋ - ਸਾਰੇ ਵਿਸ਼ਿਆਂ ਦੇ ਸਵਾਲ, ਪੂਰੇ ਸਮੇਂ ਨਾਲ।",
     "/mock"),
    ("📚 Free Study Material",
     "ਪੰਜਾਬੀ ਅਤੇ English ਵਿੱਚ ਨੋਟਸ - Punjab GK, Computer, Reasoning ਅਤੇ ਹੋਰ। ਬਿਲਕੁਲ ਮੁਫ਼ਤ।",
     "/study-material"),
    ("🗞️ Current Affairs - Monthly Magazine",
     "ਮਹੀਨੇ ਦੇ ਸਾਰੇ ਜ਼ਰੂਰੀ Current Affairs ਇੱਕ ਥਾਂ, PDF download ਅਤੇ practice set ਨਾਲ।",
     "/current-affairs"),
    ("🏅 Punjab Police SI Rank 2 ਦੀ ਪੂਰੀ ਰਣਨੀਤੀ",
     "713/800 ਨੰਬਰ ਕਿਵੇਂ ਆਏ - ਅਸਲ answer sheets, merit list ਅਤੇ ਤਿਆਰੀ ਦਾ ਪੂਰਾ blueprint।",
     "/rank-2-blueprint"),
    ("📜 ਪਿਛਲੇ ਸਾਲਾਂ ਦੇ ਪੇਪਰ",
     "ਅਸਲ ਪੇਪਰ ਦੇਖੋ ਤੇ ਸਮਝੋ ਕਿ ਸਵਾਲ ਕਿਵੇਂ ਪੁੱਛੇ ਜਾਂਦੇ ਨੇ - ਤਿਆਰੀ ਦੀ ਸਹੀ ਦਿਸ਼ਾ ਇੱਥੋਂ ਮਿਲਦੀ ਹੈ।",
     "/pyq"),
    ("🏆 Leaderboard - ਤੁਹਾਡਾ rank ਕਿੰਨਵਾਂ ਹੈ?",
     "ਟੈਸਟ ਦਿਓ ਅਤੇ ਦੇਖੋ ਪੰਜਾਬ ਦੇ ਹੋਰ aspirants ਵਿੱਚ ਤੁਸੀਂ ਕਿੱਥੇ ਖੜ੍ਹੇ ਹੋ।",
     "/leaderboard"),
    ("🌾 Punjab GK - ਪੱਕੇ ਨੰਬਰ",
     "ਪੰਜਾਬ ਦਾ ਇਤਿਹਾਸ, ਸੱਭਿਆਚਾਰ, ਭੂਗੋਲ - topic-wise MCQs ਅਤੇ ਨੋਟਸ।",
     "/subject?subject=gk&category=punjab-gk"),
    ("🧩 Reasoning practice - ਰਫ਼ਤਾਰ ਬਣਾਓ",
     "Number Series ਅਤੇ ਹੋਰ topics ਦੇ timed sets - ਹਰ ਸਵਾਲ ਨੂੰ 1 ਮਿੰਟ।",
     "/subject?subject=reasoning"),
    ("💻 Computer MCQs",
     "Fundamentals, MS Word, Mobile Phones - ਹਰ ਸਰਕਾਰੀ ਪੇਪਰ ਦਾ ਪੱਕਾ ਹਿੱਸਾ।",
     "/subject?subject=computer"),
]

CLOSERS = [
    "ਅੱਜ ਦਾ ਟੀਚਾ: ਘੱਟੋ-ਘੱਟ ਇੱਕ ਟੈਸਟ। ਕੀ ਤੁਸੀਂ ਤਿਆਰ ਹੋ? 💪",
    "ਜੋ ਅੱਜ ਸ਼ੁਰੂ ਕਰੇਗਾ, ਓਹੀ ਕੱਲ੍ਹ ਅੱਗੇ ਹੋਵੇਗਾ। ✅",
    "ਆਪਣਾ ਅੱਜ ਦਾ score comment ਵਿੱਚ ਲਿਖੋ 👇",
    "ਇਹ message ਉਸ ਦੋਸਤ ਨੂੰ ਭੇਜੋ ਜਿਸ ਨੂੰ ਅੱਜ ਹੌਸਲੇ ਦੀ ਲੋੜ ਹੈ 🤝",
    "ਸਭ ਕੁਝ ਬਿਲਕੁਲ FREE - ਬਸ ਤੁਹਾਡੀ ਮਿਹਨਤ ਚਾਹੀਦੀ ਹੈ। 🔥",
]


def compose(day):
    """The post for `day` (a date): same date, same post."""
    n = day.toordinal()
    head, body = MESSAGES[n % len(MESSAGES)]
    p_head, p_body, path = PROMOS[n % len(PROMOS)]
    closer = CLOSERS[n % len(CLOSERS)]
    return "\n".join([
        "🌅 <b>ਸ਼ੁਭ ਸਵੇਰ, Aspirants!</b>",
        "",
        f"<b>{head}</b>",
        "",
        body,
        "",
        "━━━━━━━━━━━━━━",
        f"<b>{p_head}</b>",
        p_body,
        f"👉 {SITE}{path}",
        "━━━━━━━━━━━━━━",
        "",
        closer,
        "",
        "🏠 <b>House of Aspirants</b> - Punjab Police SI Rank 2 (713/800) ਵੱਲੋਂ ਤਿਆਰ ਕੀਤਾ free platform",
        f"🌐 {SITE}",
        "#HouseOfAspirants #PunjabPolice #PSSSB #Motivation",
    ])


def send(token, chat, text):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=urllib.parse.urlencode({"chat_id": chat, "text": text,
                                     "parse_mode": "HTML",
                                     "disable_web_page_preview": "true"}).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")).get("ok", False)
    except urllib.error.HTTPError as e:
        print(f"Telegram refused the message ({e.code}): "
              f"{e.read().decode('utf-8', 'replace')[:200]}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"Telegram unreachable: {e.reason}", file=sys.stderr)
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print, do not send")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today in India)")
    a = ap.parse_args(argv)

    day = (dt.date.fromisoformat(a.date) if a.date
           else dt.datetime.now(IST).date())
    text = compose(day)
    print(text)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel = os.environ.get("TELEGRAM_CHANNEL", "").strip() or "@HouseOfAspirant"
    if a.dry_run or not token:
        print("\n[DRY RUN - nothing sent]")
        return 0
    if not send(token, channel, text):
        return 1
    owner = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
    if owner:
        plain = text.replace("<b>", "*").replace("</b>", "*")
        send(token, owner, "📋 WhatsApp ਲਈ copy ਕਰੋ:\n\n" + plain)
    print(f"\nSent to {channel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
