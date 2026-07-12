"""Social media and community sources."""
# LinkedIn removed — ToS violation; scraping LinkedIn is prohibited.
from aria.engine.collectors.social.twitter import TwitterCollector
from aria.engine.collectors.social.slack import SlackCollector

__all__ = ["TwitterCollector", "SlackCollector"]
