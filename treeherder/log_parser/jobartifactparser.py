from .logparserbase import LogParserBase


class JobArtifactParser(LogParserBase):
    """
    Gather summary information about this job.

    This parser gathers the data that shows on the bottom panel of the main
    TBPL page.

    Maintains its own state.

    """
    @property
    def name(self):
        try:
            return self.artifact["header"]["builder"]
        except KeyError:
            return "Unknown Builder"

    def parse_content(self, line):
        """Parse a single line of the log"""
        pass

    def finalize(self):
        """Do any wrap-up of this parser."""
        pass
