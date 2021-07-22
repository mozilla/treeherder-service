import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux';
import {
  Button,
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Tooltip,
  FormGroup,
  Input,
  Label,
} from 'reactstrap';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faChevronCircleDown,
  faChevronCircleUp,
  faSpinner,
  faExclamationTriangle,
} from '@fortawesome/free-solid-svg-icons';

import {
  bugzillaBugsApi,
  bzBaseUrl,
  bzComponentEndpoint,
  getApiUrl,
} from '../helpers/url';
import { create } from '../helpers/http';
import { notify } from '../job-view/redux/stores/notifications';

const crashRegex = /application crashed \[@ (.+)\]$/g;
const omittedLeads = [
  'TEST-UNEXPECTED-FAIL',
  'PROCESS-CRASH',
  'TEST-UNEXPECTED-ERROR',
  'REFTEST ERROR',
];
/*
 *  Find the first thing in the summary line that looks like a filename.
 */
const findFilename = (summary) => {
  // Take left side of any reftest comparisons, as the right side is the reference file
  // eslint-disable-next-line prefer-destructuring
  summary = summary.split('==')[0];
  // Take the leaf node of unix paths
  summary = summary.split('/').pop();
  // Take the leaf node of Windows paths
  summary = summary.split('\\').pop();
  // Remove leading/trailing whitespace
  summary = summary.trim();
  // If there's a space in what's remaining, take the first word
  // eslint-disable-next-line prefer-destructuring
  summary = summary.split(' ')[0];
  return summary;
};
/*
 *  Remove extraneous junk from the start of the summary line
 *  and try to find the failing test name from what's left
 */
const parseSummary = (suggestion) => {
  let summary = suggestion.search;
  const searchTerms = suggestion.search_terms;
  // Strip out some extra stuff at the start of some failure paths
  let re = /file:\/\/\/.*?\/build\/tests\/reftest\/tests\//gi;
  summary = summary.replace(re, '');
  re = /chrome:\/\/mochitests\/content\/a11y\//gi;
  summary = summary.replace(re, '');
  re = /http:\/\/([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):([0-9]+)\/tests\//gi;
  summary = summary.replace(re, '');
  re = /xpcshell([-a-zA-Z0-9]+)?.ini:/gi;
  summary = summary.replace(re, '');
  summary = summary.replace('/_mozilla/', 'mozilla/tests/');
  // We don't want to include "REFTEST" when it's an unexpected pass
  summary = summary.replace(
    'REFTEST TEST-UNEXPECTED-PASS',
    'TEST-UNEXPECTED-PASS',
  );
  const summaryParts = summary.split(' | ');

  // If the search_terms used for finding bug suggestions
  // contains any of the omittedLeads, that lead is needed
  // for the full string match, so don't omit it in this case.
  // If it's not needed, go ahead and omit it.
  if (searchTerms.length && summaryParts.length > 1) {
    omittedLeads.forEach((lead) => {
      if (!searchTerms[0].includes(lead) && summaryParts[0].includes(lead)) {
        summaryParts.shift();
      }
    });
  }

  // Some of the TEST-FOO bits aren't removed from the summary,
  // so we sometimes end up with them instead of the test path here.
  const summaryName =
    summaryParts[0].startsWith('TEST-') && summaryParts.length > 1
      ? summaryParts[1]
      : summaryParts[0];
  const possibleFilename = findFilename(summaryName);

  return [summaryParts, possibleFilename];
};

export class BugFilerClass extends React.Component {
  constructor(props) {
    super(props);

    const {
      suggestions,
      suggestion,
      fullLog,
      parsedLog,
      reftestUrl,
      jobGroupName,
    } = props;

    const allFailures = suggestions.map((sugg) =>
      sugg.search
        .split(' | ')
        .filter((part) => !omittedLeads.includes(part))
        .map((item) =>
          item === 'REFTEST TEST-UNEXPECTED-PASS'
            ? 'TEST-UNEXPECTED-PASS'
            : item,
        ),
    );
    const thisFailure = allFailures.map((f) => f.join(' | ')).join('\n');

    const parsedSummary = parseSummary(suggestion);
    let summaryString = parsedSummary[0].join(' | ');
    if (jobGroupName.toLowerCase().includes('reftest')) {
      const re = /layout\/reftests\//gi;
      summaryString = summaryString.replace(re, '');
    }

    const crash = suggestion.search.match(crashRegex);
    const crashSignatures = crash
      ? [crash[0].split('application crashed ')[1]]
      : [];

    const keywords = [];
    const isAssertion = [
      /ASSERTION:/, // binary code
      /assertion fail/i, // JavaScript
      /assertion count \d+ is \w+ than expected \d+ assertion/, // layout
      /AssertionError/, // Marionette
    ].some((regexp) => regexp.test(summaryString));
    if (isAssertion) {
      keywords.push('assertion');
    }

    const checkedLogLinks = new Map([
      ['Parsed log', parsedLog],
      ['Full log', fullLog],
    ]);

    if (reftestUrl) {
      checkedLogLinks.set('Reftest URL', reftestUrl);
    }

    this.state = {
      tooltipOpen: {},
      summary: `Intermittent ${summaryString}`,
      productSearch: null,
      suggestedProducts: [],
      isFilerSummaryVisible: false,
      selectedProduct: null,
      isIntermittent: true,
      isSecurityIssue: false,
      comment: '',
      searching: false,
      // used by test
      parsedSummary, // eslint-disable-line react/no-unused-state
      checkedLogLinks,
      thisFailure,
      keywords,
      crashSignatures,
    };
  }

  componentDidMount() {
    this.checkForSecurityIssue();
    this.findProductByPath();
  }

  getUnhelpfulSummaryReason(summary) {
    const { suggestion } = this.props;
    const searchTerms = suggestion.search_terms;

    if (searchTerms.length === 0) {
      return 'Selected failure does not contain any searchable terms.';
    }
    if (searchTerms.every((term) => !summary.includes(term))) {
      return "Summary does not include the full text of any of the selected failure's search terms:";
    }
    return '';
  }

  // Some job types are special, lets explicitly handle them.
  getSpecialProducts(fp) {
    const { jobGroupName } = this.props;
    const { suggestedProducts } = this.state;
    const newProducts = [];

    if (suggestedProducts.length === 0) {
      const jg = jobGroupName.toLowerCase();

      if (jg.includes('talos')) {
        newProducts.push('Testing :: Talos');
      }
      if (
        jg.includes('mochitest') &&
        (fp.includes('webextensions/') || fp.includes('components/extensions'))
      ) {
        newProducts.push('WebExtensions :: General');
      }
      if (jg.includes('mochitest') && fp.includes('webrtc/')) {
        newProducts.push('Core :: WebRTC');
      }
    }
    return newProducts;
  }

  /**
   *  'enter' from the product search input should initiate the search
   */
  productSearchEnter = (ev) => {
    const { keyCode, target } = ev;

    this.setState({ productSearch: target.value }, () => {
      if (keyCode === 13) {
        this.findProduct();
      }
    });
  };

  /*
   *  Attempt to find a good product/component for this failure
   */
  findProduct = async () => {
    const { productSearch } = this.state;

    if (!productSearch) {
      return;
    }

    let suggestedProductsSet = new Set();

    this.setState({ searching: true });

    const resp = await fetch(
      `${bzBaseUrl}rest/prod_comp_search/find/${productSearch}?limit=5`,
    );
    const data = await resp.json();
    const products = data.products.filter(
      (item) => !!item.product && !!item.component,
    );
    suggestedProductsSet = new Set([
      ...suggestedProductsSet,
      ...products.map(
        (prod) =>
          prod.product + (prod.component ? ` :: ${prod.component}` : ''),
      ),
    ]);

    const newSuggestedProducts = [...suggestedProductsSet];

    this.setState({
      suggestedProducts: newSuggestedProducts,
      selectedProduct: newSuggestedProducts[0],
      searching: false,
    });
  };

  /*
   *  Attempt to find the product/component for this failure based on the
   *  file path or its end.
   */
  findProductByPath = async () => {
    const { suggestion } = this.props;
    const pathEnd = suggestion.path_end;

    if (!pathEnd) {
      return;
    }

    let suggestedProductsSet = new Set();

    this.setState({ searching: true });

    const resp = await fetch(
      `/api${bzComponentEndpoint}?path=${encodeURIComponent(pathEnd)}`,
    );
    const data = await resp.json();
    const products = data.filter((item) => !!item.product && !!item.component);
    suggestedProductsSet = new Set([
      ...suggestedProductsSet,
      ...products.map(
        (prod) =>
          prod.product + (prod.component ? ` :: ${prod.component}` : ''),
      ),
    ]);
    const newSuggestedProducts = [...suggestedProductsSet];

    this.setState({
      suggestedProducts: newSuggestedProducts,
      selectedProduct: newSuggestedProducts[0],
      searching: false,
    });
  };

  toggleCheckedLogLink = (name, link) => {
    const { checkedLogLinks } = this.state;
    const newCheckedLogLinks = new Map(checkedLogLinks);
    if (newCheckedLogLinks.has(name)) {
      newCheckedLogLinks.delete(name);
    } else {
      newCheckedLogLinks.set(name, link);
    }

    this.setState({ checkedLogLinks: newCheckedLogLinks });
  };

  /*
   *  Actually send the gathered information to bugzilla.
   */
  submitFiler = async () => {
    const {
      summary,
      selectedProduct,
      comment,
      isIntermittent,
      isSecurityIssue,
      checkedLogLinks,
      regressedBy,
      seeAlso,
      keywords,
      crashSignatures,
    } = this.state;
    const { toggle, successCallback, notify } = this.props;

    if (!selectedProduct) {
      notify(
        'Please select (or search and select) a product/component pair to continue',
        'danger',
      );
      return;
    }
    const [product, component] = selectedProduct.split(' :: ');

    if (summary.length > 255) {
      notify(
        'Please ensure the summary is no more than 255 characters',
        'danger',
      );
      return;
    }

    // Format links in bugzilla markdown:
    //   **Parsed log:** http://...
    //   **Full log:** http://....
    const logLinks = [...checkedLogLinks]
      .map((e) => {
        const [name, url] = e;
        return `**${name}:** ${url}`;
      })
      .join('\n');

    // Join that with the comment separated with a hard rule.
    const descriptionStrings = `${logLinks}\n\n---\n\`\`\`\n${comment}\n\`\`\``;

    if (isIntermittent) {
      keywords.push('intermittent-failure');
    }
    let priority = 'P5';
    const crashSignature = crashSignatures.join('\n');

    if (crashSignature.length > 0) {
      keywords.push('crash');
      // Set no priority for crashes to get them included in triage meetings.
      priority = '--';
    }

    // Use of 'Regressed By' field shall add 'regression' to keywords.
    if (regressedBy) {
      keywords.push('regression');
    }

    /* Intermittent bugs in the Core :: DOM: Security component need to have the
       whiteboard '[domsecurity-intermittent]' to support filtering by the
       triagers. Contact person is Christoph Kerschbaumer. */
    const whiteboard =
      isIntermittent && product === 'Core' && component === 'DOM: Security'
        ? '[domsecurity-intermittent]'
        : '';

    // Bug in these components shall never get a priority automatically set
    // to let the bugs show up during triage. See bug 1580287.
    const noPriorityProdComp = [
      { product: 'Firefox', component: 'Messaging System' },
    ];
    if (
      noPriorityProdComp.some(
        (object) =>
          object.product === product && object.component === component,
      )
    ) {
      priority = '--';
    }

    // Fetch product information from bugzilla to get version numbers, then
    // submit the new bug.  Only request the versions because some products
    // take quite a long time to fetch the full object
    try {
      const productResp = await fetch(
        bugzillaBugsApi(`product/${product}`, { include_fields: 'versions' }),
      );
      const productData = await productResp.json();
      if (productResp.ok) {
        const productObject = productData.products[0];
        // Find the newest version for the product that is_active
        const version = productObject.versions
          .filter((prodVer) => prodVer.is_active)
          .slice(-1)[0];
        const payload = {
          product,
          component,
          summary,
          keywords,
          whiteboard,
          version: version.name,
          regressed_by: regressedBy,
          see_also: seeAlso,
          crash_signature: crashSignature,
          severity: 'S4',
          priority,
          groups: isSecurityIssue ? ['core-security'] : [],
          comment: descriptionStrings,
          comment_tags: 'treeherder',
        };

        const { data, failureStatus } = await create(
          getApiUrl('/bugzilla/create_bug/'),
          payload,
        );

        if (!failureStatus) {
          toggle();
          successCallback(data);
        } else {
          this.submitFailure('Treeherder Bug Filer API', failureStatus, data);
        }
      } else {
        this.submitFailure(
          'Bugzilla',
          productResp.status,
          productResp.statusText,
          productData,
        );
      }
    } catch (e) {
      notify(`Error filing bug: ${e.toString()}`, 'danger', { sticky: true });
    }
  };

  submitFailure = (source, status, statusText, data) => {
    const { notify } = this.props;

    let failureString = `${source} returned status ${status}(${statusText})`;
    if (data && data.failure) {
      failureString += `\n\n${data.failure}`;
    }
    if (status === 403) {
      failureString +=
        '\n\nAuthentication failed. Has your Treeherder session expired?';
    }
    notify(failureString, 'danger', { sticky: true });
  };

  toggleTooltip = (key) => {
    const { tooltipOpen } = this.state;
    this.setState({
      tooltipOpen: { ...tooltipOpen, [key]: !tooltipOpen[key] },
    });
  };

  checkForSecurityIssue() {
    const { comment, isSecurityIssue, summary } = this.state;

    if (isSecurityIssue) {
      return;
    }

    const inputToCheck = `${summary}\n${comment}`;

    const potentialSecurityIssues = [
      'access-violation',
      'data race',
      'double-free',
      'e5e5e5e5',
      'global-buffer-overflow',
      'heap-buffer-overflow',
      'heap-use-after-free',
      'negative-size-param',
      'stack-buffer-overflow',
      'use-after-poison',
    ];
    for (const searchTerm of potentialSecurityIssues) {
      if (inputToCheck.includes(searchTerm)) {
        this.setState({ isSecurityIssue: true });
        break;
      }
    }
  }

  render() {
    const {
      isOpen,
      toggle,
      suggestion,
      parsedLog,
      fullLog,
      reftestUrl,
    } = this.props;
    const {
      productSearch,
      suggestedProducts,
      thisFailure,
      isFilerSummaryVisible,
      isIntermittent,
      isSecurityIssue,
      summary,
      searching,
      checkedLogLinks,
      tooltipOpen,
      selectedProduct,
    } = this.state;
    const searchTerms = suggestion.search_terms;
    const crash = summary.match(crashRegex);
    const crashSignatures = crash
      ? [crash[0].split('application crashed ')[1]]
      : [];
    const unhelpfulSummaryReason = this.getUnhelpfulSummaryReason(summary);

    return (
      <div>
        <Modal isOpen={isOpen} toggle={toggle} size="lg">
          <ModalHeader toggle={toggle}>Intermittent Bug Filer</ModalHeader>
          <ModalBody>
            <form className="d-flex flex-column">
              <div className="d-inline-flex">
                <Input
                  name="modalProductFinderSearch"
                  id="modalProductFinderSearch"
                  onKeyDown={this.productSearchEnter}
                  onChange={(evt) =>
                    this.setState({ productSearch: evt.target.value })
                  }
                  type="text"
                  placeholder="e.g. Firefox, Toolkit, Testing"
                  className="flex-fill flex-grow-1"
                />
                <Tooltip
                  target="modalProductFinderSearch"
                  isOpen={tooltipOpen.modalProductFinderSearch}
                  toggle={() => this.toggleTooltip('modalProductFinderSearch')}
                >
                  Manually search for a product
                </Tooltip>
                <Button
                  color="secondary"
                  className="ml-1 btn-sm"
                  type="button"
                  onClick={this.findProduct}
                >
                  Find Product
                </Button>
              </div>
              <div>
                {!!productSearch && searching && (
                  <div>
                    <FontAwesomeIcon
                      icon={faSpinner}
                      pulse
                      className="th-spinner-lg"
                      title="Searching..."
                    />
                    Searching {productSearch}
                  </div>
                )}
                <FormGroup tag="fieldset" className="mt-1">
                  {suggestedProducts.map((product) => (
                    <div
                      className="ml-4"
                      key={`modalProductSuggestion${product}`}
                    >
                      <Label check>
                        <Input
                          type="radio"
                          value={product}
                          checked={product === selectedProduct}
                          onChange={(evt) =>
                            this.setState({ selectedProduct: evt.target.value })
                          }
                          name="productGroup"
                        />
                        {product}
                      </Label>
                    </div>
                  ))}
                </FormGroup>
              </div>
              <Label for="summary">Summary:</Label>
              <div className="d-flex">
                {!!unhelpfulSummaryReason && (
                  <div>
                    <div className="text-danger">
                      <FontAwesomeIcon
                        icon={faExclamationTriangle}
                        id="unhelpful-summary-reason"
                      />
                      Warning: {unhelpfulSummaryReason}
                      <Tooltip
                        target="unhelpful-summary-reason"
                        isOpen={tooltipOpen.unhelpfulSummaryReason}
                        toggle={() =>
                          this.toggleTooltip('unhelpfulSummaryReason')
                        }
                      >
                        This can cause poor bug suggestions to be generated
                      </Tooltip>
                    </div>
                    {searchTerms.map((term) => (
                      <div className="text-monospace pl-3" key={term}>
                        {term}
                      </div>
                    ))}
                  </div>
                )}
                <Input
                  id="summary"
                  className="flex-grow-1"
                  type="text"
                  placeholder="Intermittent..."
                  pattern=".{0,255}"
                  onChange={(evt) =>
                    this.setState({ summary: evt.target.value }, () =>
                      this.checkForSecurityIssue(),
                    )
                  }
                  value={summary}
                />
                <Tooltip
                  target="toggle-failure-lines"
                  isOpen={tooltipOpen.toggleFailureLines}
                  toggle={() => this.toggleTooltip('toggleFailureLines')}
                >
                  {isFilerSummaryVisible
                    ? 'Hide all failure lines for this job'
                    : 'Show all failure lines for this job'}
                </Tooltip>
                <FontAwesomeIcon
                  onClick={() =>
                    this.setState({
                      isFilerSummaryVisible: !isFilerSummaryVisible,
                    })
                  }
                  icon={
                    isFilerSummaryVisible
                      ? faChevronCircleUp
                      : faChevronCircleDown
                  }
                  size="lg"
                  className="pointable align-bottom pt-2 ml-1"
                  id="toggle-failure-lines"
                  title={isFilerSummaryVisible ? 'collapse' : 'expand'}
                />
                <span
                  id="summaryLength"
                  className={`ml-1 font-weight-bold lg ${
                    summary.length > 255 ? 'text-danger' : 'text-success'
                  }`}
                >
                  {summary.length}
                </span>
              </div>
              {isFilerSummaryVisible && (
                <span>
                  <Input
                    className="w-100"
                    type="textarea"
                    value={thisFailure}
                    readOnly
                    onChange={(evt) =>
                      this.setState({ thisFailure: evt.target.value })
                    }
                  />
                </span>
              )}
              <div className="ml-5 mt-2">
                <div>
                  <Label>
                    <Input
                      type="checkbox"
                      checked={checkedLogLinks.has('Parsed log')}
                      onChange={() =>
                        this.toggleCheckedLogLink('Parsed log', parsedLog)
                      }
                    />
                    <a
                      target="_blank"
                      rel="noopener noreferrer"
                      href={parsedLog}
                    >
                      Include Parsed Log Link
                    </a>
                  </Label>
                </div>
                <div>
                  <Label>
                    <Input
                      type="checkbox"
                      checked={checkedLogLinks.has('Full log')}
                      onChange={() =>
                        this.toggleCheckedLogLink('Full log', fullLog)
                      }
                    />
                    <a target="_blank" rel="noopener noreferrer" href={fullLog}>
                      Include Full Log Link
                    </a>
                  </Label>
                </div>
                {!!reftestUrl && (
                  <div>
                    <Label>
                      <Input
                        type="checkbox"
                        checked={checkedLogLinks.has('Reftest URL')}
                        onChange={() =>
                          this.toggleCheckedLogLink('Reftest URL', reftestUrl)
                        }
                      />
                      <a
                        target="_blank"
                        rel="noopener noreferrer"
                        href={reftestUrl}
                      >
                        Include Reftest Viewer Link
                      </a>
                    </Label>
                  </div>
                )}
              </div>
              <div className="d-flex flex-column">
                <Label for="summary-input">Comment:</Label>
                <Input
                  onChange={(evt) =>
                    this.setState({ comment: evt.target.value }, () =>
                      this.checkForSecurityIssue(),
                    )
                  }
                  type="textarea"
                  id="summary-input"
                  className="flex-grow-1"
                  rows={5}
                />
              </div>
              <div className="d-inline-flex mt-2 ml-5">
                <div className="mt-2">
                  <Label>
                    <Input
                      onChange={() =>
                        this.setState({ isIntermittent: !isIntermittent })
                      }
                      type="checkbox"
                      checked={isIntermittent}
                    />
                    This is an intermittent failure
                  </Label>
                </div>
                <div className="d-inline-flex ml-2">
                  <Input
                    id="regressedBy"
                    type="text"
                    className="ml-1"
                    onChange={(evt) =>
                      this.setState({ regressedBy: evt.target.value })
                    }
                    placeholder="Regressed by"
                  />
                  <Tooltip
                    target="regressedBy"
                    placement="bottom"
                    isOpen={tooltipOpen.regressedBy}
                    toggle={() => this.toggleTooltip('regressedBy')}
                  >
                    Comma-separated list of bugs
                  </Tooltip>
                  <Input
                    id="seeAlso"
                    className="ml-1"
                    type="text"
                    onChange={(evt) =>
                      this.setState({ seeAlso: evt.target.value })
                    }
                    placeholder="See also"
                  />
                  <Tooltip
                    target="seeAlso"
                    placement="bottom"
                    isOpen={tooltipOpen.seeAlso}
                    toggle={() => this.toggleTooltip('seeAlso')}
                  >
                    Comma-separated list of bugs
                  </Tooltip>
                </div>
              </div>
              <div className="d-inline-flex mt-2 ml-5">
                <Label>
                  <Input
                    id="securityIssue"
                    onChange={() =>
                      this.setState({ isSecurityIssue: !isSecurityIssue })
                    }
                    type="checkbox"
                    checked={isSecurityIssue}
                  />
                  Report this as a security issue
                </Label>
              </div>
              {!!crashSignatures.length && (
                <div>
                  <Label for="signature-input">Signature:</Label>
                  <Input
                    type="textarea"
                    id="signature-input"
                    onChange={(evt) =>
                      this.setState({ crashSignatures: evt.target.value })
                    }
                    maxLength="2048"
                    readOnly
                    value={crashSignatures.join('\n')}
                  />
                </div>
              )}
            </form>
          </ModalBody>
          <ModalFooter>
            <Button color="secondary" onClick={this.submitFiler}>
              Submit Bug
            </Button>{' '}
            <Button color="secondary" onClick={toggle}>
              Cancel
            </Button>
          </ModalFooter>
        </Modal>
      </div>
    );
  }
}

BugFilerClass.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  toggle: PropTypes.func.isRequired,
  suggestion: PropTypes.shape({}).isRequired,
  suggestions: PropTypes.arrayOf(PropTypes.object).isRequired,
  fullLog: PropTypes.string.isRequired,
  parsedLog: PropTypes.string.isRequired,
  reftestUrl: PropTypes.string.isRequired,
  successCallback: PropTypes.func.isRequired,
  jobGroupName: PropTypes.string.isRequired,
  notify: PropTypes.func.isRequired,
};

export default connect(null, { notify })(BugFilerClass);
