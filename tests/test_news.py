import unittest
from financialjuice_bot.news import parse_rss


RSS = b'''<?xml version="1.0"?><rss><channel><item><title>FOMC update</title><description><![CDATA[<b>Powell</b> speaks]]></description><link>https://example.com/a</link><guid>a</guid><pubDate>Wed, 02 Sep 2026 16:00:00 GMT</pubDate></item></channel></rss>'''


class NewsTests(unittest.TestCase):
    def test_parse(self):
        items = parse_rss(RSS)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].event_id, "a")
        self.assertEqual(items[0].title, "FOMC update")


if __name__ == "__main__":
    unittest.main()
