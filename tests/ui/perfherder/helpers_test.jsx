import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';

import { getTitle, getFrameworkName } from '../../../ui/perfherder/helpers';

const alertSummaryInput = {
  id: 29117,
  push_id: 874307,
  prev_push_id: 874305,
  created: '2021-03-08T14:06:40.615547',
  repository: 'autoland',
  framework: 6,
  alerts: [
    {
      id: 114649,
      status: 0,
      series_signature: {
        id: 2845721,
        framework_id: 6,
        signature_hash: '8c31442e0ad30d5d2d9b2a14dbe2699e7ad8facc',
        machine_platform: 'macosx1014-64-qr',
        suite: 'Strings',
        test: 'PerfUTF16toUTF8KOFifteen',
        lower_is_better: true,
        has_subtests: false,
        option_collection_hash: '102210fe594ee9b33d82058545b1ed14f4c8206e',
      },
      is_regression: false,
      prev_value: 2144.58,
      new_value: 2085.5,
      t_value: 26.47,
      amount_abs: -59.08,
      amount_pct: 2.76,
      summary_id: 29117,
      related_summary_id: null,
      manually_created: false,
      classifier: null,
      starred: false,
      classifier_email: null,
      backfill_record: null,
      title: 'Strings PerfUTF16toUTF8KOFifteen macosx1014-64-qr opt ',
    },
    {
      id: 114635,
      status: 0,
      series_signature: {
        id: 2845673,
        framework_id: 6,
        signature_hash: '2308ba944f5ef56e6d88d3b56f5ea3805c32e9c2',
        machine_platform: 'macosx1014-64-qr',
        suite: 'Strings',
        test: 'PerfUTF16toUTF8ARThousand',
        lower_is_better: true,
        has_subtests: false,
        option_collection_hash: '102210fe594ee9b33d82058545b1ed14f4c8206e',
      },
      is_regression: false,
      prev_value: 110647.92,
      new_value: 104710.67,
      t_value: 14.93,
      amount_abs: -5937.25,
      amount_pct: 5.37,
      summary_id: 29117,
      related_summary_id: null,
      manually_created: false,
      classifier: null,
      starred: false,
      classifier_email: null,
      backfill_record: null,
      title: 'Strings PerfUTF16toUTF8ARThousand macosx1014-64-qr opt ',
    },
    {
      id: 114631,
      status: 0,
      series_signature: {
        id: 2845628,
        framework_id: 6,
        signature_hash: '362b6a058ed9c58286c87510f8633dab0ae7469b',
        machine_platform: 'macosx1014-64-qr',
        suite: 'Strings',
        test: 'PerfIsUTF8Hundred',
        lower_is_better: true,
        has_subtests: false,
        option_collection_hash: '102210fe594ee9b33d82058545b1ed14f4c8206e',
      },
      is_regression: true,
      prev_value: 2215.38,
      new_value: 2632.58,
      t_value: 13.19,
      amount_abs: 417.21,
      amount_pct: 18.83,
      summary_id: 29117,
      related_summary_id: null,
      manually_created: false,
      classifier: null,
      starred: false,
      classifier_email: null,
      backfill_record: null,
      title: 'Strings PerfIsUTF8Hundred macosx1014-64-qr opt ',
    },
    {
      id: 114632,
      status: 0,
      series_signature: {
        id: 2845632,
        framework_id: 6,
        signature_hash: 'd15d9acbb8137a532732174f95799c5c4f0219e3',
        machine_platform: 'macosx1014-64-qr',
        suite: 'Strings',
        test: 'PerfIsASCIIHundred',
        lower_is_better: true,
        has_subtests: false,
        option_collection_hash: '102210fe594ee9b33d82058545b1ed14f4c8206e',
      },
      is_regression: true,
      prev_value: 2829.21,
      new_value: 2914.75,
      t_value: 13.55,
      amount_abs: 85.54,
      amount_pct: 3.02,
      summary_id: 29117,
      related_summary_id: null,
      manually_created: false,
      classifier: null,
      starred: false,
      classifier_email: null,
      backfill_record: null,
      title: 'Strings PerfIsASCIIHundred macosx1014-64-qr opt ',
    },
  ],
  related_alerts: [],
  status: 0,
  bug_number: null,
  bug_updated: null,
  issue_tracker: 1,
  notes: null,
  revision: 'c7760ee4f8e2f5f2d263067b7a206c976a188d0b',
  push_timestamp: 1615153736,
  prev_push_revision: 'f2186e9a7ba59fa686498082fad9759a0d43d76a',
  assignee_username: null,
  assignee_email: null,
  performance_tags: [],
};

test('getTitle', async () => {
  const result = getTitle(alertSummaryInput);
});
