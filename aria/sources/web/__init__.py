"""Web search and general web collection sources."""
from aria.engine.collectors.web.search import WebSearchCollector
from aria.engine.collectors.web.reddit import RedditCollector
from aria.engine.collectors.web.hackernews import HackerNewsCollector
from aria.engine.collectors.web.wikipedia import WikipediaCollector
from aria.engine.collectors.web.medium import MediumCollector
from aria.engine.collectors.web.devto import DevToCollector
from aria.engine.collectors.web.substack import SubstackCollector
from aria.engine.collectors.web.rss import RSSCollector
from aria.engine.collectors.web.pdf import PDFCollector
__all__ = ["WebSearchCollector","RedditCollector","HackerNewsCollector","WikipediaCollector","MediumCollector","DevToCollector","SubstackCollector","RSSCollector","PDFCollector"]
