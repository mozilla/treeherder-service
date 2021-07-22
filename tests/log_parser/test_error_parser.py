import pytest

from treeherder.log_parser.parsers import ErrorParser

ERROR_TEST_CASES = (
    # "TEST-UNEXPECTED-"
    "23:52:39 INFO - 346 INFO TEST-UNEXPECTED-FAIL | dom/base/test/test_XHRDocURI.html | foo",
    # "fatal error"
    "c:/Users/task_1584487163/dist/Release/lib\\softokn3.dll.lib : fatal error LNK1120: 2 unresolved externals",
    # "FATAL ERROR"
    "20:10:13     INFO - PID 15468 | FATAL ERROR: AsyncShutdown timeout in xpcom-will-shutdown",
    # "Hit MOZ_CRASH"
    "15:28:28     INFO - GECKO(3166) | Hit MOZ_CRASH(Shutdown hanging after all known phases and workers finished.) at /builds/worker/checkouts/gecko/toolkit/components/terminator/nsTerminator.cpp:246",
    # "PROCESS-CRASH"
    "00:54:55 WARNING - PROCESS-CRASH | Shutdown | application crashed [@ PR_GetThreadPrivate]",
    # "Assertion fail"
    "GECKO(6227) | Assertion failure: parent, at /builds/worker/checkouts/gecko/docshell/base/BrowsingContext.cpp:1365",
    # "^\d+:\d+:\d+ +(?:ERROR|CRITICAL|FATAL) - "
    "23:57:52 ERROR - Return code: 1",
    # "^\d+:\d+:\d+ +(?:ERROR|CRITICAL|FATAL) - "
    "23:57:52 CRITICAL - Preparing to abort run due to failed verify check.",
    # "^\d+:\d+:\d+ +(?:ERROR|CRITICAL|FATAL) - "
    "23:57:52 FATAL - Dying due to failing verification",
    # ^remoteFailed:"
    "remoteFailed: [Failure instance: Traceback (failure with no frames): Foo.",
    # "^g?make(?:\[\d+\])?: \*\*\*"
    "08:13:37 INFO - make: *** [test-integration-test] Error 1",
    # "mozmake\.(?:exe|EXE)(?:\[\d+\])?: \*\*\*"
    r"pymake\..\..\mozmake.exe: *** [buildsymbols] Error 11",
    # "mozmake\.(?:exe|EXE)(?:\[\d+\])?: \*\*\*"
    r"pymake\..\..\mozmake.EXE: *** [buildsymbols] Error 11",
    # "SUMMARY: AddressSanitizer"
    "00:55:13 INFO - SUMMARY: AddressSanitizer: 64 byte(s) leaked in 1 allocation(s).",
    # "SUMMARY: ThreadSanitizer"
    "INFO - GECKO(2552) | SUMMARY: ThreadSanitizer: data race /builds/worker/checkouts/gecko/js/src/gc/Cell.h:572:21 in lengthField",
    # "SUMMARY: UndefinedBehaviorSanitizer"
    "04:48:03     INFO -  [webrender 0.61.0] SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior glsl-optimizer/src/compiler/glsl/glcpp/pp.c:198:28 in",
    # "ThreadSanitizer: nested bug"
    "19:34:37     INFO - GECKO(2516) | ThreadSanitizer: nested bug in the same thread, aborting.",
    # "Automation Error:"
    "Automation Error: Foo bar",
    # "command timed out:"
    "22:16:31     INFO -  command timed out: fake -f param",
    # "wget: unable "
    "22:16:31     INFO -  wget: unable to resolve host address `queue.taskcluster.net'",
    # "^g?make(?:\[\d+\])?: \*\*\*"
    "20:57:49    ERROR -  make[3]: *** [widget/gtk/target-objects] Error 2",
    # "^[A-Za-z.]+Error: "
    "subprocess.CalledProcessError: Command '['/usr/bin/python3', 'doc', '--outdir', 'docs-out', '--no-open', '--no-serve', '--archive']' returned non-zero exit status 2.",
    # "^[A-Za-z\.]*Exception: "
    "InvalidArgumentException: Unknown pointerType: [object String]",
    # "^abort: "
    "abort: reached maximum number of network attempts; giving up",
    # "^rm: cannot "
    "rm: cannot remove `debian/git/usr/share/doc/git/contrib': Is a directory",
    # "^\[taskcluster\] Error:"
    "[taskcluster] Error: Task run time exceeded 7200 seconds.",
    # "ERROR [45]\d\d:"
    "2014-04-04 06:37:57 ERROR 403: Forbidden.",
    # "^\[[\w._-]+:(?:error|exception)\]"
    "[taskcluster:error] Could not upload artifact",
    # "^\[[\w._-]+:(?:error|exception)\]"
    "[taskcluster-image-build:error] Dockerfile must be present in /home/worker/nss/automation.",
    # "^\[[\w._-]+:(?:error|exception)\]"
    "[test_linux.sh:error] could not download zip file",
    # "REFTEST ERROR"
    "14:15:32     INFO -  REFTEST ERROR | file:///Z:/task_1491573689/build/tests/reftest/tests/layout/reftests/w3c-css/submitted/text3/text-justify-inter-character-001.html | application timed out after 330 seconds with no output",
    # "|^\[  FAILED  \] "
    "[  FAILED  ] AllHashFuncs/TlsHkdfTest.HkdfNullNull/1, where GetParam() = 5"
    # "bash.exe: *** "
    "[task 2019-01-07T09:43:24.098Z] C:\\mozilla-build\\msys\\bin\\bash.exe: *** Couldn't reserve space for cygwin's heap, Win32 error 0",
    # " error\(\d*\):"
    "12:54:44     INFO -  ChunkedEncodingError: (\"Connection broken: error(54, 'Connection reset by peer')\", error(54, 'Connection reset by peer'))",
    # ":\d+: error:"
    "2020-03-18 20:40:52 UTC 39:27.50 /builds/worker/checkouts/gecko/widget/gtk/nsWindow.cpp:3536:30: error: too few arguments to function 'const gchar* gtk_check_version(guint, guint, guint)'",
    # " error R?C\d*:"
    "src/gl.cc(2249): error C2065: 'BLEND_1': undeclared identifier",
    # "YOU ARE LEAKING THE WORLD"
    "20:28:29     INFO - WARNING: YOU ARE LEAKING THE WORLD (at least one JSRuntime and everything alive inside it, that is) AT JS_ShutDown TIME.  FIX THIS!",
)

NON_ERROR_TEST_CASES = (
    # General message for a passing test step
    "TEST-PASS | foo | bar",
    # Doesn't match "^[A-Za-z\.]*Exception: "
    "07:42:02     INFO -  Exception:",
    # Doesn't match "^[A-Za-z.]+Error: "
    "07:51:08     INFO -  Caught Exception: Remote Device Error: unable to connect to panda-0501 after 5 attempts",
    # "I[ /](Gecko|TestRunner).*TEST-UNEXPECTED-"
    "06:21:18     INFO -  I/GeckoDump(  730): 110 INFO TEST-UNEXPECTED-FAIL | foo | bar",
    # Doesn't match "^\[taskcluster\] Error:"
    "[taskcluster:info] Starting task",
    # Doesn't match "^\[[\w._-]+:(?:error|exception)\]"
    "[taskcluster] Starting task",
    # "^ImportError: No module named pygtk$"
    "01:22:41     INFO -  ImportError: No module named pygtk",
    # "^ImportError: No module named pygtk$"
    "01:22:41     INFO -  ImportError: No module named pygtk\r\n",
    # "^non-fatal error"
    "non-fatal error removing directory: Contents/_CodeSignature/, rv: 0, err: 39",
)


@pytest.mark.parametrize("line", ERROR_TEST_CASES)
def test_error_lines_matched(line):
    parser = ErrorParser()
    is_error_line = parser.is_error_line(line)
    assert is_error_line

    # Now feed the line into the parser and verify we still find an error.
    parser.parse_line(line, 1)
    assert len(parser.artifact) == 1


@pytest.mark.parametrize("line", ERROR_TEST_CASES)
def test_error_lines_taskcluster(line):
    parser = ErrorParser()
    # Make the log parser think this is a TaskCluster log.
    parser.parse_line('[taskcluster foo] this is a taskcluster log', 1)
    assert parser.is_taskcluster
    parser.parse_line(line, 2)
    assert len(parser.artifact) == 1


@pytest.mark.parametrize("line", NON_ERROR_TEST_CASES)
def test_successful_lines_not_matched(line):
    parser = ErrorParser()
    is_error_line = parser.is_error_line(line)
    assert not is_error_line


def test_taskcluster_strip_prefix():
    parser = ErrorParser()
    assert not parser.is_taskcluster
    assert not parser.artifact

    # Prefix should not be stripped unless we see a
    # [taskcluster...] line. Not stripping the prefix causes error parsing to
    # fail.
    parser.parse_line("[vcs 2016-09-07T19:03:02.188327Z] 23:57:52 ERROR - Return code: 1", 1)
    assert not parser.is_taskcluster
    assert not parser.artifact

    # Parsing a line with the [taskcluster...] prefix marks the log as
    # associated with TC.
    parser.parse_line("[taskcluster 2016-09-07 19:02:55.114Z] Task ID: PWden6jYS4SfVKYj4p7y6w", 2)
    assert parser.is_taskcluster
    assert not parser.artifact

    # And parsing the same line as above should detect the error since the
    # TC prefix is stripped.
    parser.parse_line("[vcs 2016-09-07T19:03:02.188327Z] 23:57:52 ERROR - Return code: 1", 3)
    assert len(parser.artifact) == 1
    assert parser.artifact[0]['linenumber'] == 3
