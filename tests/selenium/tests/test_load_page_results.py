# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from pages.treeherder import TreeherderPage


@pytest.mark.nondestructive
def test_load_next_results(base_url, selenium):
    page = TreeherderPage(selenium, base_url).open()
    assert len(page.result_sets) == 10

    page.get_next_ten_results()
    assert len(page.result_sets) == 20

    page.get_next_twenty_results()
    page.wait_for_page_to_load()
    assert len(page.result_sets) == 40

    page.get_next_fifty_results()
    assert len(page.result_sets) == 90
