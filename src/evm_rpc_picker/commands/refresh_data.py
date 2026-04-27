from collections.abc import AsyncIterator

from textual.command import DiscoveryHit, Hit, Provider


class RefreshDataProvider(Provider):
    """Command provider for refreshing chain data."""

    async def search(self, query: str) -> AsyncIterator[Hit]:
        """Search for the refresh command."""
        matcher = self.matcher(query)
        name = "Refresh Data from chainlist.org"
        score = matcher.match(name)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(name),
                getattr(self.screen, "action_refresh_data", lambda: None),
                help="Fetch the latest chain data from chainlist.org",
            )

    async def discover(self) -> AsyncIterator[DiscoveryHit]:
        """Discover the refresh command."""
        yield DiscoveryHit(
            "Refresh Data from chainlist.org",
            getattr(self.screen, "action_refresh_data", lambda: None),
            help="Fetch the latest chain data from chainlist.org",
        )
