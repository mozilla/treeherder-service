import pytest

from treeherder.model.error_summary import (
    get_cleaned_line,
    get_crash_signature,
    get_error_search_term_and_path,
)

LINE_CLEANING_TEST_CASES = (
    (
        (
            '00:54:20     INFO - GECKO(1943) | Assertion failure: rc != 0 '
            '(destroyed timer off its target thread!), at '
            '/builds/worker/checkouts/gecko/xpcom/threads/TimerThread.cpp:434'
        ),
        (
            'Assertion failure: rc != 0 (destroyed timer off its target thread!),'
            ' at '
            '/builds/worker/checkouts/gecko/xpcom/threads/TimerThread.cpp:434'
        ),
    ),
)


@pytest.mark.parametrize(("line_raw", "exp_line_cleaned"), LINE_CLEANING_TEST_CASES)
def test_get_cleaned_line(line_raw, exp_line_cleaned):
    """
    Test cleaning from of error line from unnecessary information, e.g.
    mozharness timestamps and process ids
    """
    actual_line_cleaned = get_cleaned_line(line_raw)
    assert actual_line_cleaned == exp_line_cleaned


PIPE_DELIMITED_LINE_TEST_CASES = (
    (
        (
            '596 INFO TEST-UNEXPECTED-FAIL '
            '| chrome://mochitests/content/browser/browser/components/loop/test/mochitest/browser_fxa_login.js '
            '| Check settings tab URL - Got http://mochi.test:8888/browser/browser/components/loop/test/mochitest/loop_fxa.sjs'
        ),
        {
            'path_end': 'chrome://mochitests/content/browser/browser/components/loop/test/mochitest/browser_fxa_login.js',
            'search_term': 'browser_fxa_login.js',
        },
    ),
    (
        (
            'REFTEST TEST-UNEXPECTED-FAIL '
            '| file:///C:/slave/test/build/tests/reftest/tests/layout/reftests/layers/component-alpha-exit-1.html '
            '| image comparison (==), max difference: 255, number of differing pixels: 251'
        ),
        {
            'path_end': 'file:///C:/slave/test/build/tests/reftest/tests/layout/reftests/layers/component-alpha-exit-1.html',
            'search_term': 'component-alpha-exit-1.html',
        },
    ),
    (
        (
            '2423 INFO TEST-UNEXPECTED-FAIL '
            '| /tests/dom/media/tests/mochitest/test_dataChannel_basicAudio.html '
            '| undefined assertion name - Result logged after SimpleTest.finish()'
        ),
        {
            'path_end': '/tests/dom/media/tests/mochitest/test_dataChannel_basicAudio.html',
            'search_term': 'test_dataChannel_basicAudio.html',
        },
    ),
    (
        (
            r"TEST-UNEXPECTED-FAIL "
            r"| mainthreadio "
            r"| File 'c:\users\cltbld~1.t-w' was accessed and we were not expecting it: {'Count': 6, 'Duration': 0.112512, 'RunCount': 6}"
        ),
        {
            'path_end': 'mainthreadio',
            'search_term': 'mainthreadio',
        },
    ),
    (
        (
            "REFTEST PROCESS-CRASH "
            "| http://10.0.2.2:8854/tests/dom/canvas/test/reftest/webgl-resize-test.html == "
            "http://10.0.2.2:8854/tests/dom/canvas/test/reftest/wrapper.html?green.png "
            "| application crashed [@ jemalloc_crash]"
        ),
        {
            'path_end': 'http://10.0.2.2:8854/tests/dom/canvas/test/reftest/webgl-resize-test.html',
            'search_term': 'webgl-resize-test.html',
        },
    ),
    (
        (
            "REFTEST PROCESS-CRASH "
            "| http://10.0.2.2:8854/tests/dom/canvas/test/reftest/webgl-resize-test.html != "
            "http://10.0.2.2:8854/tests/dom/canvas/test/reftest/wrapper.html?green.png "
            "| application crashed [@ jemalloc_crash]"
        ),
        {
            'path_end': 'http://10.0.2.2:8854/tests/dom/canvas/test/reftest/webgl-resize-test.html',
            'search_term': 'webgl-resize-test.html',
        },
    ),
    (
        (
            "TEST-UNEXPECTED-FAIL "
            "| /tests/dom/events/test/pointerevents/pointerevent_touch-action-table-test_touch-manual.html "
            "| touch-action attribute test on the cell: assert_true: scroll received while shouldn't expected true got false"
        ),
        {
            'path_end': '/tests/dom/events/test/pointerevents/pointerevent_touch-action-table-test_touch-manual.html',
            'search_term': 'pointerevent_touch-action-table-test_touch-manual.html',
        },
    ),
)


@pytest.mark.parametrize(("line", "exp_search_info"), PIPE_DELIMITED_LINE_TEST_CASES)
def test_get_delimited_search_term(line, exp_search_info):
    """Test search term extraction for a pipe delimited error line"""
    actual_search_info = get_error_search_term_and_path(line)
    assert actual_search_info == exp_search_info


LEAK_LINE_TEST_CASES = (
    (
        (
            'TEST-UNEXPECTED-FAIL '
            '| leakcheck | 13195 bytes leaked '
            '(BackstagePass, CallbackObject, DOMEventTargetHelper, '
            'EventListenerManager, EventTokenBucket, ...)'
        ),
        {
            'path_end': None,
            'search_term': 'BackstagePass, CallbackObject, DOMEventTargetHelper, EventListenerManager, EventTokenBucket, ...',
        },
    ),
    (
        (
            'TEST-UNEXPECTED-FAIL '
            '| leakcheck | tab process: 44330 bytes leaked '
            '(AsyncLatencyLogger, AsyncTransactionTrackersHolder, AudioOutputObserver, '
            'BufferRecycleBin, CipherSuiteChangeObserver, ...)'
        ),
        {
            'path_end': None,
            'search_term': 'AsyncLatencyLogger, AsyncTransactionTrackersHolder, AudioOutputObserver, BufferRecycleBin, CipherSui',
        },
    ),
    (
        (
            'TEST-UNEXPECTED-FAIL '
            '| LeakSanitizer | leak at '
            'MakeUnique, nsThread::nsChainedEventQueue::nsChainedEventQueue, nsThread, nsThreadManager::Init'
        ),
        {
            'path_end': None,
            'search_term': 'MakeUnique, nsThread::nsChainedEventQueue::nsChainedEventQueue, nsThread, nsThreadManager::Init',
        },
    ),
)


@pytest.mark.parametrize(("line", "exp_search_info"), LEAK_LINE_TEST_CASES)
def test_get_leak_search_term(line, exp_search_info):
    """tests the search term extracted from a leak error line is correct"""
    actual_search_info = get_error_search_term_and_path(line)
    assert actual_search_info == exp_search_info


FULL_LINE_FALLBACK_TEST_CASES = (
    (
        'Automation Error: No crash directory (/mnt/sdcard/tests/profile/minidumps/) found on remote device',
        {
            'path_end': None,
            'search_term': 'Automation Error: No crash directory (/mnt/sdcard/tests/profile/minidumps/) found on remote device',
        },
    ),
    (
        'PROCESS-CRASH | Automation Error: Missing end of test marker (process crashed?)',
        {
            'path_end': None,
            'search_term': 'Automation Error: Missing end of test marker (process crashed?)',
        },
    ),
)


@pytest.mark.parametrize(("line", "exp_search_info"), FULL_LINE_FALLBACK_TEST_CASES)
def test_get_full_line_search_term(line, exp_search_info):
    """Test that the full error line is used as a fall-back if no test name found"""
    actual_search_info = get_error_search_term_and_path(line)
    assert actual_search_info == exp_search_info


LONG_LINE_TEST_CASES = (
    (
        (
            'command timed out: 2400 seconds without output running '
            '[\'/tools/buildbot/bin/python\', '
            '\'scripts/scripts/android_emulator_unittest.py\', \'--cfg\', '
            '\'android/androidx86.py\', \'--test-suite\', \'robocop-1\', '
            '\'--test-suite\', \'robocop-2\', \'--test-suite\', \'robocop-3\', '
            '\'--test-suite\', \'xpcshell\', \'--blob-upload-branch\', '
            '\'b2g-inbound\', \'--download-symbols\', \'ondemand\'], '
            'attempting to kill'
        ),
        {
            'path_end': None,
            'search_term': 'command timed out: 2400 seconds without output running '
            '[\'/tools/buildbot/bin/python\', \'scripts/scrip',
        },
    ),
    (
        (
            'TEST-UNEXPECTED-FAIL '
            '| test_switch_frame.py TestSwitchFrame.test_should_be_able_to_carry_on_working_if_the_frame_is_deleted_from_under_us '
            '| AssertionError: 0 != 1'
        ),
        {
            'path_end': 'test_switch_frame.py TestSwitchFrame.test_should_be_able_to_carry_on_working_if_the_frame_is_deleted_from_under_us',
            'search_term': 'test_switch_frame.py TestSwitchFrame.test_should_be_able_to_carry_on_working_if_the_frame_is_deleted',
        },
    ),
)

# command timed out: 2400 seconds without output running ['/tools/buildbot/bin/python', 'scripts/scripts/android_emulator_unittest.py', '--cfg', 'android/androidx86.py', '--test-suite', 'robocop-1', '--test-suite', 'robocop-2', '--test-suite', 'robocop-3', '--test-suite', 'xpcshell', '--blob-upload-branch', 'b2g-inbound', '--download-symbols', 'ondemand'], attempting to kill


@pytest.mark.parametrize(("line", "exp_search_info"), LONG_LINE_TEST_CASES)
def test_get_long_search_term(line, exp_search_info):
    """tests that long search terms are capped at 100 characters"""
    actual_search_info = get_error_search_term_and_path(line)
    assert actual_search_info == exp_search_info


CRASH_LINE_TEST_CASES = (
    (
        (
            'PROCESS-CRASH | file:///C:/slave/test/build/tests/jsreftest/tests/'
            'jsreftest.html?test=test262/ch11/11.4/11.4.1/11.4.1-4.a-6.js | '
            'application crashed [@ nsInputStreamPump::OnStateStop()]'
        ),
        'nsInputStreamPump::OnStateStop()',
    ),
)


@pytest.mark.parametrize(("line", "exp_search_info"), CRASH_LINE_TEST_CASES)
def test_get_crash_signature(line, exp_search_info):
    """tests the search term extracted from an error line is correct"""
    actual_search_info = get_crash_signature(line)
    assert actual_search_info == exp_search_info


BLACKLIST_TEST_CASES = (
    (
        'TEST-UNEXPECTED-FAIL | remoteautomation.py | application timed out after 330 seconds with no output',
        {
            'path_end': 'remoteautomation.py',
            'search_term': 'remoteautomation.py | application timed out after 330 seconds with no output',
        },
    ),
    (
        'Return code: 1',
        {
            'path_end': None,
            'search_term': None,
        },
    ),
    (
        (
            'REFTEST PROCESS-CRASH | file:///home/worker/workspace/build/tests/reftest/tests/layout/reftests/font-inflation/video-1.html '
            '| application crashed [@ mozalloc_abort]'
        ),
        {
            'path_end': 'file:///home/worker/workspace/build/tests/reftest/tests/layout/reftests/font-inflation/video-1.html',
            'search_term': 'video-1.html',
        },
    ),
)


@pytest.mark.parametrize(("line", "exp_search_info"), BLACKLIST_TEST_CASES)
def test_get_blacklisted_search_term(line, exp_search_info):
    """Test search term extraction for lines that contain a blacklisted term"""
    actual_search_info = get_error_search_term_and_path(line)
    assert actual_search_info == exp_search_info
