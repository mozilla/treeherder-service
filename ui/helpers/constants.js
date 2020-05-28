import treeFavicon from '../img/tree_open.png';
import closedTreeFavicon from '../img/tree_closed.png';

// TODO: This file is a handy catch-all, but we could likely move some of these
// to a specific helper or into the classes that use them.

export const thPlatformMap = {
  linux32: 'Linux',
  'linux32-devedition': 'Linux DevEdition',
  'linux32-nightly': 'Linux Nightly',
  'linux32-shippable': 'Linux shippable',
  'linux1804-32-shippable': 'Linux 18.04 shippable',
  linux64: 'Linux x64',
  'linux1804-64-tsan': 'Linux 18.04 x64 tsan',
  'linux64-asan': 'Linux x64 asan',
  'linux64-asan-qr': 'Linux x64 WebRender asan',
  'linux64-asan-reporter': 'Linux x64 asan reporter',
  'linux64-add-on-devel': 'Linux x64 addon',
  'linux64-devedition': 'Linux x64 DevEdition',
  'linux64-shippable-qr': 'Linux x64 WebRender Shippable',
  'linux64-qr': 'Linux x64 WebRender',
  'linux64-nightly': 'Linux x64 Nightly',
  'linux64-shippable': 'Linux x64 shippable',
  'linux64-ccov': 'Linux x64 CCov',
  'linux64-noopt': 'Linux x64 NoOpt',
  'linux64-aarch64': 'Linux AArch64',
  'linux1804-64': 'Linux 18.04 x64',
  'linux1804-64-asan': 'Linux 18.04 x64 asan',
  'linux1804-64-asan-qr': 'Linux 18.04 x64 WebRender asan',
  'linux1804-64-devedition': 'Linux 18.04 x64 DevEdition',
  'linux1804-64-shippable-qr': 'Linux 18.04 x64 WebRender Shippable',
  'linux1804-64-qr': 'Linux 18.04 x64 WebRender',
  'linux1804-64-shippable': 'Linux 18.04 x64 shippable',
  'linux1804-64-ccov': 'Linux 18.04 x64 CCov',
  'osx-1014-64': 'OS X 10.14',
  'osx-cross': 'OS X Cross Compiled',
  'osx-1014-64-shippable': 'OS X 10.14 shippable',
  'osx-shippable': 'OS X Cross Compiled shippable',
  'osx-cross-noopt': 'OS X Cross Compiled NoOpt',
  'osx-cross-add-on-devel': 'OS X Cross Compiled addon',
  'osx-cross-ccov': 'OS X Cross Compiled CCov',
  'osx-cross-devedition': 'OS X Cross Compiled DevEdition',
  'macosx1014-64': 'OS X 10.14',
  'macosx1014-64-qr': 'OS X 10.14 WebRender',
  'macosx1014-64-shippable': 'OS X 10.14 Shippable',
  'macosx1014-64-shippable-qr': 'OS X 10.14 WebRender Shippable',
  'macosx1014-64-devedition': 'OS X 10.14 DevEdition',
  'macosx1014-64-nightly': 'OS X 10.14 Nightly',
  'macosx1014-64-ccov': 'OS X 10.14 Cross Compiled CCov',
  'windows7-32': 'Windows 7',
  'windows7-32-devedition': 'Windows 7 DevEdition',
  'windows7-32-nightly': 'Windows 7 VM Nightly',
  'windows7-32-shippable': 'Windows 7 Shippable',
  'windows7-32-mingwclang': 'Windows 7 MinGW',
  'windows10-64': 'Windows 10 x64',
  'windows10-64-ccov': 'Windows 10 x64 CCov',
  'windows10-64-devedition': 'Windows 10 x64 DevEdition',
  'windows10-64-nightly': 'Windows 10 x64 Nightly',
  'windows10-64-shippable': 'Windows 10 x64 Shippable',
  'windows10-64-shippable-qr': 'Windows 10 x64 WebRender Shippable',
  'windows10-64-qr': 'Windows 10 x64 WebRender',
  'windows10-64-ref-hw-2017': 'Windows 10 x64 2017 Ref HW',
  'windows10-64-mingwclang': 'Windows 10 x64 MinGW',
  'windows10-aarch64': 'Windows 10 AArch64',
  'windows2012-32': 'Windows 2012',
  'windows2012-32-shippable': 'Windows 2012 shippable',
  'windows2012-32-add-on-devel': 'Windows 2012 addon',
  'windows2012-32-noopt': 'Windows 2012 NoOpt',
  'windows2012-32-devedition': 'Windows 2012 DevEdition',
  'windows2012-64': 'Windows 2012 x64',
  'windows2012-64-shippable': 'Windows 2012 x64 shippable',
  'windows2012-aarch64': 'Windows 2012 AArch64',
  'windows2012-aarch64-shippable': 'Windows 2012 AArch64 Shippable',
  'windows2012-aarch64-devedition': 'Windows 2012 AArch64 DevEdition',
  'win64-asan-reporter': 'Windows 2012 x64 asan reporter',
  'windows2012-64-add-on-devel': 'Windows 2012 x64 addon',
  'windows2012-64-noopt': 'Windows 2012 x64 NoOpt',
  'windows2012-64-devedition': 'Windows 2012 x64 DevEdition',
  'windows-mingw32': 'Windows MinGW',

  'android-4-0-armv7-api16': 'Android 4.0 API16+',
  'android-4-0-armv7-api16-beta': 'Android 4.0 API16+ Beta',
  'android-4-0-armv7-api16-release': 'Android 4.0 API16+ Release',
  'android-4-0-armv7-api16-shippable': 'Android 4.0 API16+ Shippable',
  'android-4-0-armv7-api16-ccov': 'Android 4.0 API16+ CCov',
  'android-4-0-geckoview-fat-aar':
    'Android 4.0 API16+ GeckoView multi-arch fat AAR',
  'android-4-0-geckoview-fat-aar-shippable':
    'Android 4.0 API16+ Shippable GeckoView multi-arch fat AAR',
  'android-4-2-x86': 'Android 4.2 x86',
  'android-4-2-x86-beta': 'Android 4.2 x86 Beta',
  'android-4-2-x86-release': 'Android 4.2 x86 Release',
  'android-4-2-x86-shippable': 'Android 4.2 x86 Shippable',
  'android-em-4-2-x86': 'Android 4.2 x86',
  'android-em-4-2-x86-beta': 'Android 4.2 x86 Beta',
  'android-em-4-2-x86-release': 'Android 4.2 x86 Release',
  'android-em-4-3-armv7-api16': 'Android 4.3 API16+',
  'android-em-4-3-armv7-api16-beta': 'Android 4.3 API16+ Beta',
  'android-em-4-3-armv7-api16-ccov': 'Android 4.3 API16+ CCov',
  'android-em-4-3-armv7-api16-release': 'Android 4.3 API16+ Release',
  'android-5-0-aarch64': 'Android 5.0 AArch64',
  'android-5-0-aarch64-beta': 'Android 5.0 AArch64 Beta',
  'android-5-0-aarch64-release': 'Android 5.0 AArch64 Release',
  'android-5-0-aarch64-shippable': 'Android 5.0 AArch64 Shippable',
  'android-5-0-x86_64': 'Android 5.0 x86-64',
  'android-5-0-x86_64-beta': 'Android 5.0 x86-64 Beta',
  'android-5-0-x86_64-release': 'Android 5.0 x86-64 Release',
  'android-em-7-0-x86': 'Android 7.0 x86',
  'android-em-7-0-x86-beta': 'Android 7.0 x86 Beta',
  'android-em-7-0-x86-release': 'Android 7.0 x86 Release',
  'android-em-7-0-x86_64': 'Android 7.0 x86-64',
  'android-em-7-0-x86_64-qr': 'Android 7.0 x86-64 WebRender',
  'android-em-7-0-x86_64-beta': 'Android 7.0 x86-64 Beta',
  'android-em-7-0-x86_64-release': 'Android 7.0 x86-64 Release',
  'android-hw-g5-7-0-arm7-api-16': 'Android 7.0 MotoG5',
  'android-hw-p2-8-0-arm7-api-16': 'Android 8.0 Pixel2',
  'android-hw-p2-8-0-arm7-api-16-qr': 'Android 8.0 Pixel2 WebRender',
  'android-hw-p2-8-0-arm7-api-16-nightly': 'Android 8.0 Pixel2 Nightly',
  'android-hw-p2-8-0-arm7-api-16-shippable': 'Android 8.0 Pixel2 Shippable',
  'android-hw-p2-8-0-android-aarch64': 'Android 8.0 Pixel2 AArch64',
  'android-hw-p2-8-0-android-aarch64-qr':
    'Android 8.0 Pixel2 AArch64 WebRender',
  'android-hw-p2-8-0-android-aarch64-nightly':
    'Android 8.0 Pixel2 AArch64 Nightly',
  Android: 'Android',

  'gecko-decision': 'Gecko Decision Task',
  'firefox-release': 'Firefox Release Tasks',
  'devedition-release': 'Devedition Release Tasks',
  'fennec-beta': 'Fennec Beta Tasks',
  'fennec-release': 'Fennec Release Tasks',
  'thunderbird-release': 'Thunderbird Release Tasks',
  diff: 'Diffoscope',
  lint: 'Linting',
  fetch: 'Fetch',
  'taskcluster-images': 'Docker Images',
  packages: 'Packages',
  toolchains: 'Toolchains',
  other: 'Other',
};

// Platforms where the `opt` should be dropped from
export const thSimplePlatforms = [
  'gecko-decision',
  'firefox-release',
  'devedition-release',
  'fennec-beta',
  'fennec-release',
  'thunderbird-release',
  'lint',
  'taskcluster-images',
  'packages',
  'toolchains',
  'diff',
];

export const thFailureResults = ['testfailed', 'busted', 'exception'];

export const thAllResultStatuses = [
  'testfailed',
  'busted',
  'exception',
  'success',
  'retry',
  'usercancel',
  'superseded',
  'running',
  'pending',
  'runnable',
];

export const thOptionOrder = {
  opt: 1,
  pgo: 2,
  asan: 3,
  tsan: 4,
  debug: 5,
  cc: 6,
  addon: 7,
  all: 8,
};

export const thFavicons = {
  closed: closedTreeFavicon,
  open: treeFavicon,
  'approval required': treeFavicon,
  unavailable: treeFavicon,
};

export const thDefaultRepo = 'autoland';

export const thJobNavSelectors = {
  ALL_JOBS: {
    name: 'jobs',
    selector: '.job-btn, .selected-job, .selected-count',
  },
  UNCLASSIFIED_FAILURES: {
    name: 'unclassified failures',
    selector:
      '.selected-job, .job-btn.btn-red, .job-btn.btn-orange, .job-btn.btn-purple',
  },
};

export const thPerformanceBranches = ['autoland', 'mozilla-inbound'];

/**
 * The set of custom Treeherder events.
 */
export const thEvents = {
  // fired with a selected job on 't'
  selectNextTab: 'select-next-tab-EVT',
  // fired with a selected job on 'r'
  jobRetrigger: 'job-retrigger-EVT',
  // fired when job classifications change (created/deleted)
  classificationChanged: 'classification-changed-EVT',
  saveClassification: 'save-classification-EVT',
  deleteClassification: 'delete-classification-EVT',
  openLogviewer: 'open-logviewer-EVT',
  applyNewJobs: 'apply-new-jobs-EVT',
  filtersUpdated: 'filters-updated-EVT',
  clearPinboard: 'clear-pinboard-EVT',
};

export const thBugSuggestionLimit = 20;

export const thMaxPushFetchSize = 100;

export const errorMessageClass = 'text-danger py-4 d-block text-center';

export const genericErrorMessage = 'Something went wrong';
