from cerely import task

from treeherder.seta.analyze_failures import AnalyzeFailures


@task(name='seta-analyze-failures', time_limit=20*60)
def seta_analyze_failures():
    '''We analyze the starred test failures of the last 90 days which were fixed by a commit.'''
    AnalyzeFailures().run()
