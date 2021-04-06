import React from 'react';
import { mount } from 'enzyme/build';
import fetchMock from 'fetch-mock';

import { bzComponentEndpoint, bzBaseUrl } from '../../../ui/helpers/url';
import { isReftest } from '../../../ui/helpers/job';
import { BugFilerClass } from '../../../ui/shared/BugFiler';

describe('BugFiler', () => {
  const fullLog =
    'https://taskcluster.net/api/queue/v1/task/AGs4CgN_RnCTb943uQn8NQ/runs/0/artifacts/public/logs/live_backing.log';
  const parsedLog =
    'http://localhost:5000/logviewer.html#?job_id=89017089&repo=mozilla-inbound';
  const reftest = '';
  const selectedJob = {
    job_group_name: 'Mochitests executed by TaskCluster',
    job_type_name: 'test-linux64/debug-mochitest-browser-chrome-10',
    job_type_symbol: 'bc10',
  };
  const suggestions = [
    { search: 'ShutdownLeaks | process() called before end of test suite' },
    {
      search:
        'browser/components/search/test/browser_searchbar_smallpanel_keyboard_navigation.js | application terminated with exit code 11',
    },
    {
      search:
        'browser/components/search/test/browser_searchbar_smallpanel_keyboard_navigation.js | application crashed [@ js::GCMarker::eagerlyMarkChildren]',
    },
    {
      search:
        'leakcheck | default process: missing output line for total leaks!',
    },
    { search: '# TBPL FAILURE #' },
  ];
  const successCallback = () => {};
  const toggle = () => {};
  const isOpen = true;

  beforeEach(() => {
    fetchMock.mock(
      `/api${bzComponentEndpoint}?path=browser%2Fextensions%2Fpdfjs%2Ftest%2Fbrowser_pdfjs_views.js`,
      [
        {
          product: 'Mock Product',
          component: 'Mock Component',
        },
      ],
    );

    fetchMock.mock(
      `${bzBaseUrl}rest/prod_comp_search/find/firefox%20::%20search?limit=5`,
      {
        products: [
          { product: 'Firefox' },
          { component: 'Search', product: 'Firefox' },
          { product: 'Marketplace' },
          { component: 'Search', product: 'Marketplace' },
          { product: 'Firefox for Android' },
          { component: 'Search Activity', product: 'Firefox for Android' },
          { product: 'Firefox OS' },
          { component: 'Gaia::Search', product: 'Firefox OS' },
          { product: 'Cloud Services' },
          { component: 'Operations: Storage', product: 'Cloud Services' },
        ],
      },
    );
  });

  afterEach(() => {
    fetchMock.reset();
  });

  const getBugFilerForSummary = (summary) => {
    const suggestion = {
      summary,
      search_terms: [
        'browser_searchbar_smallpanel_keyboard_navigation.js", "[@ js::GCMarker::eagerlyMarkChildren]',
      ],
      search: summary,
    };

    return mount(
      <BugFilerClass
        isOpen={isOpen}
        toggle={toggle}
        suggestion={suggestion}
        suggestions={suggestions}
        fullLog={fullLog}
        parsedLog={parsedLog}
        reftestUrl={isReftest(selectedJob) ? reftest : ''}
        successCallback={successCallback}
        jobGroupName={selectedJob.job_group_name}
        notify={() => {}}
      />,
    );
  };

  const getBugFilerForSecurityCheck = (suggestions) => {
    return mount(
      <BugFilerClass
        isOpen={isOpen}
        toggle={toggle}
        suggestion={suggestions[0]}
        suggestions={suggestions}
        fullLog={fullLog}
        parsedLog={parsedLog}
        reftestUrl={isReftest(selectedJob) ? reftest : ''}
        successCallback={successCallback}
        jobGroupName={selectedJob.job_group_name}
        notify={() => {}}
      />,
    );
  };

  test('suggested product retrieved and when bugfiler gets opened', async () => {
    const suggestions = [
      {
        bugs: {},
        line_number: 10,
        path_end: 'browser/extensions/pdfjs/test/browser_pdfjs_views.js',
        search_terms: [],
        search:
          'TEST-UNEXPECTED-FAIL | browser/extensions/pdfjs/test/browser_pdfjs_views.js | Test timed out -',
      },
      {
        bugs: {},
        line_number: 235,
        path_end: 'browser/extensions/pdfjs/test/browser_pdfjs_views.js',
        search_terms: [],
        search:
          'TEST-UNEXPECTED-FAIL | browser/extensions/pdfjs/test/browser_pdfjs_views.js | Found a tab after previous test timed out: about:blank -',
      },
      {
        bugs: {},
        line_number: 783,
        path_end: 'flee',
        search_terms: [],
        search: 'REFTEST TEST-UNEXPECTED-PASS | flee | floo',
      },
    ];
    const bugFiler = mount(
      <BugFilerClass
        isOpen={isOpen}
        toggle={toggle}
        suggestion={suggestions[0]}
        suggestions={suggestions}
        fullLog={fullLog}
        parsedLog={parsedLog}
        reftestUrl={isReftest(selectedJob) ? reftest : ''}
        successCallback={successCallback}
        jobGroupName={selectedJob.job_group_name}
        notify={() => {}}
      />,
    );

    await bugFiler
      .instance()
      .findProductByPath(bugFiler.props().suggestion.path_end);
    const { suggestedProducts } = bugFiler.state();
    expect(suggestedProducts).toHaveLength(1);
    expect(suggestedProducts).toEqual(['Mock Product :: Mock Component']);
  });

  test('parses a crash suggestion', () => {
    const summary =
      'PROCESS-CRASH | browser/components/search/test/browser_searchbar_smallpanel_keyboard_navigation.js | application crashed [@ js::GCMarker::eagerlyMarkChildren]';
    const bugFiler = getBugFilerForSummary(summary);
    const { parsedSummary } = bugFiler.state();
    expect(parsedSummary[0][0]).toEqual(
      'browser/components/search/test/browser_searchbar_smallpanel_keyboard_navigation.js',
    );
  });

  test('should parse mochitest-bc summaries', () => {
    const rawSummary =
      'browser/components/sessionstore/test/browser_625016.js | observe1: 1 window in data written to disk - Got 0, expected 1';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe(
      'browser/components/sessionstore/test/browser_625016.js',
    );
    expect(summary[0][1]).toBe(
      'observe1: 1 window in data written to disk - Got 0, expected 1',
    );
    expect(summary[1]).toBe('browser_625016.js');
  });

  test('should parse accessibility summaries', () => {
    const rawSummary =
      'chrome://mochitests/content/a11y/accessible/tests/mochitest/states/test_expandable.xul' +
      ' | uncaught exception - TypeError: this.textbox.popup.oneOffButtons is undefined at ' +
      'searchbar_XBL_Constructor@chrome://browser/content/search/search.xml:95:9';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe(
      'accessible/tests/mochitest/states/test_expandable.xul',
    );
    expect(summary[0][1]).toBe(
      'uncaught exception - TypeError: this.textbox.popup.oneOffButtons is undefined at ' +
        'searchbar_XBL_Constructor@chrome://browser/content/search/search.xml:95:9',
    );
    expect(summary[1]).toBe('test_expandable.xul');
  });

  test('should parse xpcshell summaries', () => {
    const rawSummary =
      'xpcshell-child-process.ini:dom/indexedDB/test/unit/test_rename_objectStore_errors.js | application crashed [@ mozalloc_abort(char const*)]';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe(
      'dom/indexedDB/test/unit/test_rename_objectStore_errors.js',
    );
    expect(summary[0][1]).toBe(
      'application crashed [@ mozalloc_abort(char const*)]',
    );
    expect(summary[1]).toBe('test_rename_objectStore_errors.js');
  });

  test('should parse xpcshell unpack summaries', () => {
    const rawSummary =
      'xpcshell-unpack.ini:dom/indexedDB/test/unit/test_rename_objectStore_errors.js | application crashed [@ mozalloc_abort(char const*)]';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe(
      'dom/indexedDB/test/unit/test_rename_objectStore_errors.js',
    );
    expect(summary[0][1]).toBe(
      'application crashed [@ mozalloc_abort(char const*)]',
    );
    expect(summary[1]).toBe('test_rename_objectStore_errors.js');
  });

  test('should parse xpcshell dom summaries', () => {
    const rawSummary =
      'xpcshell.ini:dom/indexedDB/test/unit/test_rename_objectStore_errors.js | application crashed [@ mozalloc_abort(char const*)]';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe(
      'dom/indexedDB/test/unit/test_rename_objectStore_errors.js',
    );
    expect(summary[0][1]).toBe(
      'application crashed [@ mozalloc_abort(char const*)]',
    );
    expect(summary[1]).toBe('test_rename_objectStore_errors.js');
  });

  test('should parse Windows reftests on C drive summaries', () => {
    const rawSummary =
      'file:///C:/slave/test/build/tests/reftest/tests/layout/reftests/w3c-css/submitted/variables/variable-supports-12.html | application timed out after 330 seconds with no output';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe(
      'layout/reftests/w3c-css/submitted/variables/variable-supports-12.html',
    );
    expect(summary[0][1]).toBe(
      'application timed out after 330 seconds with no output',
    );
    expect(summary[1]).toBe('variable-supports-12.html');
  });

  test('should parse Linux reftest summaries', () => {
    const rawSummary =
      'file:///home/worker/workspace/build/tests/reftest/tests/image/test/reftest/encoders-lossless/size-7x7.png | application timed out after 330 seconds with no output';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe(
      'image/test/reftest/encoders-lossless/size-7x7.png',
    );
    expect(summary[0][1]).toBe(
      'application timed out after 330 seconds with no output',
    );
    expect(summary[1]).toBe('size-7x7.png');
  });

  test('should parse Windows reftests on Z drive summaries', () => {
    const rawSummary =
      'file:///Z:/task_1491428153/build/tests/reftest/tests/layout/reftests/font-face/src-list-local-full.html == file:///Z:/task_1491428153/build/tests/reftest/tests/layout/reftests/font-face/src-list-local-full-ref.html | image comparison, max difference: 255, number of differing pixels: 5184';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe(
      'layout/reftests/font-face/src-list-local-full.html == layout/reftests/font-face/src-list-local-full-ref.html',
    );
    expect(summary[0][1]).toBe(
      'image comparison, max difference: 255, number of differing pixels: 5184',
    );
    expect(summary[1]).toBe('src-list-local-full.html');
  });

  test('should parse android reftests summaries', () => {
    const rawSummary =
      'http://10.0.2.2:8854/tests/layout/reftests/css-display/display-contents-style-inheritance-1.html == http://10.0.2.2:8854/tests/layout/reftests/css-display/display-contents-style-inheritance-1-ref.html | image comparison, max difference: 255, number of differing pixels: 699';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe(
      'layout/reftests/css-display/display-contents-style-inheritance-1.html == layout/reftests/css-display/display-contents-style-inheritance-1-ref.html',
    );
    expect(summary[0][1]).toBe(
      'image comparison, max difference: 255, number of differing pixels: 699',
    );
    expect(summary[1]).toBe('display-contents-style-inheritance-1.html');
  });

  test('should parse reftest unexpected pass summaries', () => {
    const rawSummary =
      'REFTEST TEST-UNEXPECTED-PASS | file:///home/worker/workspace/build/tests/reftest/tests/layout/' +
      'reftests/backgrounds/vector/empty/wide--cover--width.html == file:///home/worker/workspace/' +
      'build/tests/reftest/tests/layout/reftests/backgrounds/vector/empty/ref-wide-lime.html | image comparison';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe('TEST-UNEXPECTED-PASS');
    expect(summary[0][1]).toBe(
      'layout/reftests/backgrounds/vector/empty/wide--cover--width.html == layout/reftests/backgrounds/vector/empty/ref-wide-lime.html',
    );
    expect(summary[0][2]).toBe('image comparison');
    expect(summary[1]).toBe('wide--cover--width.html');
  });

  test('should set as security bug if summary contains initially a relevant search term', () => {
    const suggestions = [
      {
        bugs: {},
        search_terms: [],
        search:
          'SUMMARY: AddressSanitizer: heap-use-after-free /builds/worker/checkouts/gecko/mock/folder/file.c:12:34 in mock::MockComponent::MockMethod(mock::squirrel::Weasel*)',
      },
    ];
    const bugFiler = getBugFilerForSecurityCheck(suggestions);
    expect(bugFiler.state().isSecurityIssue).toBe(true);
  });

  test('should not set as security bug if summary contains initially no relevant search term', () => {
    const suggestions = [
      {
        bugs: {},
        search_terms: [],
        search:
          'TEST-UNEXPECTED-FAIL | mock/folder/test/subfolder/browser_test.js | Test timed out -',
      },
    ];
    const bugFiler = getBugFilerForSecurityCheck(suggestions);
    expect(bugFiler.state().isSecurityIssue).toBe(false);
  });

  test('should parse finding the filename when the `TEST-FOO` is not omitted', () => {
    const rawSummary =
      'TEST-UNEXPECTED-CRASH | /service-workers/service-worker/xhr.https.html | expected OK';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const summary = bugFiler.state().parsedSummary;
    expect(summary[0][0]).toBe('TEST-UNEXPECTED-CRASH');
    expect(summary[0][1]).toBe(
      '/service-workers/service-worker/xhr.https.html',
    );
    expect(summary[0][2]).toBe('expected OK');
    expect(summary[1]).toBe('xhr.https.html');
  });

  test('should set "assertion" keyword if summary contains "assertion fail"', () => {
    const rawSummary =
      'Assertion failure: [GFX1]: Failed to create software bitmap: Size(16,8) Code: 0x8899000c, at z:/build/build/src/obj-firefox/dist/include/mozilla/gfx/Logging.h:740';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const { keywords } = bugFiler.state();
    expect(keywords).toEqual(expect.arrayContaining(['assertion']));
  });

  test('should set "assertion" keyword if summary contains "ASSERTION:"', () => {
    const rawSummary =
      "ASSERTION: No list accessible for listitem accessible!: 'Error', filemozilla/accessible/xul/XULListboxAccessible.cpp, line 478";
    const bugFiler = getBugFilerForSummary(rawSummary);
    const { keywords } = bugFiler.state();
    expect(keywords).toEqual(expect.arrayContaining(['assertion']));
  });

  test('should set "assertion" keyword if summary contains "assertion count d+ is w+ than expected d+ assertion"', () => {
    const rawSummary =
      'REFTEST TEST-UNEXPECTED-FAIL | http://10.0.2.2:8854/tests/layout/generic/crashtests/847209.html | assertion count 6 is more than expected 4 assertions';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const { keywords } = bugFiler.state();
    expect(keywords).toEqual(expect.arrayContaining(['assertion']));
  });

  test('should set "assertion" keyword if summary contains "AssertionError"', () => {
    const rawSummary =
      'TEST-UNEXPECTED-FAIL | testing/marionette/harness/marionette_harness/tests/unit/test_window_rect.py TestWindowRect.test_set_position_and_size | AssertionError: 0 != 10';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const { keywords } = bugFiler.state();
    expect(keywords).toEqual(expect.arrayContaining(['assertion']));
  });

  test('should not set "assertion" keyword if summary contains none', () => {
    const rawSummary =
      'TEST-UNEXPECTED-FAIL | browser/base/content/test/performance/browser_tabdetach.js | unexpected reflow at scrollByPixels@chrome://global/content/elements/arrowscrollbox.js hit 1 times';
    const bugFiler = getBugFilerForSummary(rawSummary);
    const { keywords } = bugFiler.state();
    expect(keywords).toEqual(expect.not.arrayContaining(['assertion']));
  });

  test('should strip omitted leads from thisFailure', () => {
    const suggestions = [
      {
        bugs: {},
        search_terms: [],
        search:
          'TEST-UNEXPECTED-FAIL | browser/extensions/pdfjs/test/browser_pdfjs_views.js | Test timed out -',
      },
      {
        bugs: {},
        search_terms: [],
        search:
          'TEST-UNEXPECTED-FAIL | browser/extensions/pdfjs/test/browser_pdfjs_views.js | Found a tab after previous test timed out: about:blank -',
      },
      {
        bugs: {},
        search_terms: [],
        search: 'REFTEST TEST-UNEXPECTED-PASS | flee | floo',
      },
    ];
    const bugFiler = mount(
      <BugFilerClass
        isOpen={isOpen}
        toggle={toggle}
        suggestion={suggestions[0]}
        suggestions={suggestions}
        fullLog={fullLog}
        parsedLog={parsedLog}
        reftestUrl={isReftest(selectedJob) ? reftest : ''}
        successCallback={successCallback}
        jobGroupName={selectedJob.job_group_name}
        notify={() => {}}
      />,
    );

    const { thisFailure } = bugFiler.state();
    expect(thisFailure).toBe(
      'browser/extensions/pdfjs/test/browser_pdfjs_views.js | Test timed out -\n' +
        'browser/extensions/pdfjs/test/browser_pdfjs_views.js | Found a tab after previous test timed out: about:blank -\n' +
        'TEST-UNEXPECTED-PASS | flee | floo',
    );
  });
});
