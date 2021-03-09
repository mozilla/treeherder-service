import pytest

from treeherder.model.models import BugzillaComponent, FilesBugzillaMap, Repository
from treeherder.etl.files_bugzilla_map import FilesBugzillaMapProcess

EXPECTED_PROJECTS = [
    'mozilla-central',
    'mozilla-beta',
    'mozilla-release',
    'mozilla-esr78',
]


@pytest.mark.django_db(transaction=True)
def test_get_project_to_import(setup_repository_data):
    """
    Test for which projects the mapping of files to Bugzilla components shall be
    imported and if the order is correct.
    """
    actual_projects = list(
        Repository.objects.filter(codebase='gecko')
        .filter(active_status='active')
        .filter(life_cycle_order__isnull=False)
        .values_list('name', flat=True)
        .order_by('life_cycle_order')
    )
    assert actual_projects == EXPECTED_PROJECTS


# def test_data_ingestion(transactional_db, mock_file_bugzilla_map_request):
@pytest.mark.django_db(transaction=True)
def test_data_ingestion(setup_repository_data, mock_file_bugzilla_map_request):
    """
    Test data for relevant projects gets imported, only the one for the most
    recent project (on a per file base) stored and unused data evicted during
    the next import.
    """
    import_process = FilesBugzillaMapProcess()
    import_process.run_id = "import_1"
    import_process.run()
    assert FilesBugzillaMap.objects.count() == 7

    EXPECTED_FILES_BUGZILLA_DATA_IMPORT_1 = [
        ('AUTHORS', 'AUTHORS', 'mozilla.org', 'Licensing'),
        ('browser/components/BrowserGlue.jsm', 'BrowserGlue.jsm', 'Firefox', 'General'),
        (
            'mozilla-esr78-folder/file.new.here',
            'file.new.here',
            'Mock Component',
            'File only present in mozilla-esr78',
        ),
        (
            'otherfolder/AUTHORS',
            'AUTHORS',
            'mozilla.org',
            'Different path, same product, different component',
        ),
        (
            'testing/web-platform/meta/IndexedDB/historical.html.ini',
            'historical.html.ini',
            'Testing',
            'web-platform-tests',
        ),
        (
            'testing/web-platform/tests/IndexedDB/historical.html',
            'historical.html',
            'Core',
            'Storage: IndexedDB',
        ),
        (
            'toolkit/mozilla-beta/fantasy_file.js',
            'fantasy_file.js',
            'Mock',
            'File first seen on mozilla-beta',
        ),
    ]
    assert EXPECTED_FILES_BUGZILLA_DATA_IMPORT_1 == list(
        FilesBugzillaMap.objects.all()
        .values_list(
            'path', 'file_name', 'bugzilla_component__product', 'bugzilla_component__component'
        )
        .order_by('path')
    )

    EXPECTED_BUGZILLA_COMPONENTS_IMPORT_1 = [
        ('Core', 'Storage: IndexedDB'),
        ('Firefox', 'General'),
        ('Mock', 'File first seen on mozilla-beta'),
        ('Mock Component', 'File only present in mozilla-esr78'),
        ('Testing', 'web-platform-tests'),
        ('mozilla.org', 'Different path, same product, different component'),
        ('mozilla.org', 'Licensing'),
    ]
    assert EXPECTED_BUGZILLA_COMPONENTS_IMPORT_1 == list(
        BugzillaComponent.objects.all()
        .values_list('product', 'component')
        .order_by('product', 'component')
    )

    import_process.run_id = "import_2"
    import_process.run()
    assert FilesBugzillaMap.objects.count() == 6

    EXPECTED_FILES_BUGZILLA_DATA_IMPORT_2 = [
        ('AUTHORS', 'AUTHORS', 'mozilla.org', 'Import 2: same product, different component'),
        ('browser/components/BrowserGlue.jsm', 'BrowserGlue.jsm', 'Firefox', 'General'),
        (
            'testing/web-platform/meta/IndexedDB/historical.html.ini',
            'historical.html.ini',
            'Testing',
            'web-platform-tests',
        ),
        (
            'testing/web-platform/tests/IndexedDB/historical.html',
            'historical.html',
            'Core',
            'Storage: IndexedDB',
        ),
        (
            'testing/web-platform/tests/IndexedDB2/historical.html',
            'historical.html',
            'Core',
            'Storage: IndexedDB2',
        ),
        (
            'toolkit/mozilla-beta/fantasy_file.js',
            'fantasy_file.js',
            'Mock (import 2)',
            'File first seen on mozilla-beta',
        ),
    ]
    assert EXPECTED_FILES_BUGZILLA_DATA_IMPORT_2 == list(
        FilesBugzillaMap.objects.all()
        .values_list(
            'path', 'file_name', 'bugzilla_component__product', 'bugzilla_component__component'
        )
        .order_by('path')
    )

    print(
        list(
            BugzillaComponent.objects.all()
            .values_list('product', 'component')
            .order_by('product', 'component')
        )
    )
    EXPECTED_BUGZILLA_COMPONENTS_IMPORT_2 = [
        ('Core', 'Storage: IndexedDB'),
        ('Core', 'Storage: IndexedDB2'),
        ('Firefox', 'General'),
        ('Mock (import 2)', 'File first seen on mozilla-beta'),
        ('Testing', 'web-platform-tests'),
        ('mozilla.org', 'Import 2: same product, different component'),
    ]
    assert EXPECTED_BUGZILLA_COMPONENTS_IMPORT_2 == list(
        BugzillaComponent.objects.all()
        .values_list('product', 'component')
        .order_by('product', 'component')
    )
