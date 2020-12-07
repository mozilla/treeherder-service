import React from 'react';
import PropTypes from 'prop-types';
import { Button, Container, Col, Row } from 'reactstrap';
import unionBy from 'lodash/unionBy';
import queryString from 'query-string';

import { getData, processResponse, processErrors } from '../../helpers/http';
import {
  createApiUrl,
  parseQueryParams,
  updateQueryParams,
} from '../../helpers/url';
import {
  genericErrorMessage,
  errorMessageClass,
} from '../../helpers/constants';
import { processSelectedParam, createGraphData } from '../helpers';
import {
  endpoints,
  graphColors,
  graphSymbols,
  phTimeRanges,
  phDefaultTimeRangeValue,
} from '../constants';
import ErrorMessages from '../../shared/ErrorMessages';
import ErrorBoundary from '../../shared/ErrorBoundary';
import LoadingSpinner from '../../shared/LoadingSpinner';

import LegendCard from './LegendCard';
import GraphsViewControls from './GraphsViewControls';

class GraphsView extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      timeRange: this.getDefaultTimeRange(),
      zoom: {},
      selectedDataPoint: null,
      highlightAlerts: true,
      highlightedRevisions: ['', ''],
      testData: [],
      errorMessages: [],
      options: {},
      loading: false,
      colors: [...graphColors],
      symbols: [...graphSymbols],
      showModal: false,
      showTable: false,
      visibilityChanged: false,
    };
  }

  async componentDidMount() {
    this.checkQueryParams();
  }

  getDefaultTimeRange = () => {
    const { location } = this.props;
    const { timerange } = parseQueryParams(location.search);

    const defaultValue = timerange
      ? parseInt(timerange, 10)
      : phDefaultTimeRangeValue;
    return phTimeRanges.find((time) => time.value === defaultValue);
  };

  checkQueryParams = () => {
    const {
      series,
      zoom,
      selected,
      highlightAlerts,
      highlightedRevisions,
    } = queryString.parse(this.props.location.search);

    const updates = {};

    if (series) {
      const _series = typeof series === 'string' ? [series] : series;
      const seriesParams = this.parseSeriesParam(_series);
      this.getTestData(seriesParams, true);
    }

    if (highlightAlerts) {
      updates.highlightAlerts = Boolean(parseInt(highlightAlerts, 10));
    }

    if (highlightedRevisions) {
      updates.highlightedRevisions =
        typeof highlightedRevisions === 'string'
          ? [highlightedRevisions]
          : highlightedRevisions;
    }

    if (zoom) {
      const zoomArray = zoom.replace(/[[{}\]"]+/g, '').split(',');
      const zoomObject = {
        x: zoomArray.map((x) => new Date(parseInt(x, 10))).slice(0, 2),
        y: zoomArray.slice(2, 4),
      };
      updates.zoom = zoomObject;
    }

    if (selected) {
      const tooltipArray = selected.replace(/[[]"]/g, '').split(',');
      const tooltipValues = processSelectedParam(tooltipArray);
      updates.selectedDataPoint = tooltipValues;
    }

    this.setState(updates);
  };

  createSeriesParams = (series) => {
    const {
      repository_name: repositoryName,
      signature_id: signatureId,
      framework_id: frameworkId,
    } = series;
    const { timeRange } = this.state;

    return {
      repository: repositoryName,
      signature: signatureId,
      framework: frameworkId,
      interval: timeRange.value,
      all_data: true,
    };
  };

  getTestData = async (newDisplayedTests = [], init = false) => {
    const { testData } = this.state;
    const tests = newDisplayedTests.length ? newDisplayedTests : testData;
    this.setState({ loading: true });

    const responses = await Promise.all(
      tests.map((series) =>
        getData(
          createApiUrl(endpoints.summary, this.createSeriesParams(series)),
        ),
      ),
    );
    const errorMessages = processErrors(responses);

    if (errorMessages.length) {
      this.setState({ errorMessages, loading: false });
    } else {
      // If the server returns an empty array instead of signature data with data: [],
      // that test won't be shown in the graph or legend; this will prevent the UI from breaking
      const data = responses
        .filter((response) => response.data.length)
        .map((reponse) => reponse.data[0]);
      let newTestData = await this.createGraphObject(data);

      if (newDisplayedTests.length) {
        newTestData = [...testData, ...newTestData];
      }
      this.setState(
        { testData: newTestData, loading: false, visibilityChanged: false },
        () => {
          if (!init) {
            // we don't need to change params when getData is called on initial page load
            this.changeParams();
          }
        },
      );
    }
  };

  createGraphObject = async (seriesData) => {
    const { colors, symbols } = this.state;
    const alertSummaries = await Promise.all(
      seriesData.map((series) =>
        this.getAlertSummaries(series.signature_id, series.repository_id),
      ),
    );
    const newColors = [...colors];
    const newSymbols = [...symbols];

    const graphData = createGraphData(
      seriesData,
      alertSummaries.flat(),
      newColors,
      newSymbols,
    );

    this.setState({ colors: newColors, symbols: newSymbols });
    return graphData;
  };

  getAlertSummaries = async (signatureId, repository) => {
    const { errorMessages } = this.state;

    const data = await getData(
      createApiUrl(endpoints.alertSummary, {
        alerts__series_signature: signatureId,
        repository,
      }),
    );
    const response = processResponse(data, 'alertSummaries', errorMessages);

    if (response.alertSummaries) {
      return response.alertSummaries.results;
    }
    this.setState({ errorMessages: response.errorMessages });
    return [];
  };

  updateData = async (
    signatureId,
    repositoryName,
    alertSummaryId,
    dataPointIndex,
  ) => {
    const { testData } = this.state;

    const updatedData = testData.find(
      (test) => test.signature_id === signatureId,
    );
    const alertSummaries = await this.getAlertSummaries(
      signatureId,
      repositoryName,
    );
    const alertSummary = alertSummaries.find(
      (result) => result.id === alertSummaryId,
    );
    updatedData.data[dataPointIndex].alertSummary = alertSummary;
    const newTestData = unionBy([updatedData], testData, 'signature_id');

    this.setState({ testData: newTestData });
  };

  parseSeriesParam = (series) =>
    series.map((encodedSeries) => {
      const partialSeriesArray = encodedSeries.split(',');
      const partialSeriesObject = {
        repository_name: partialSeriesArray[0],
        // TODO deprecate signature_hash
        signature_id:
          partialSeriesArray[1] && partialSeriesArray[1].length === 40
            ? partialSeriesArray[1]
            : parseInt(partialSeriesArray[1], 10),
        // TODO partialSeriesArray[2] is for the 1 that's inserted in the url
        // for visibility of test legend cards but isn't actually being used
        // to control visibility so it should be removed at some point
        framework_id: parseInt(partialSeriesArray[3], 10),
      };

      return partialSeriesObject;
    });

  toggle = (state) => {
    this.setState((prevState) => ({
      [state]: !prevState[state],
    }));
  };

  updateParams = (params) => {
    const { location, history } = this.props;
    let newQueryString = queryString.stringify(params);
    newQueryString = newQueryString.replace(/%2C/g, ',');

    updateQueryParams(newQueryString, history, location);
  };

  changeParams = () => {
    const {
      testData,
      selectedDataPoint,
      zoom,
      highlightAlerts,
      highlightedRevisions,
      timeRange,
    } = this.state;

    const newSeries = testData.map(
      (series) =>
        `${series.repository_name},${series.signature_id},1,${series.framework_id}`,
    );
    const params = {
      series: newSeries,
      highlightAlerts: +highlightAlerts,
      timerange: timeRange.value,
      zoom,
    };

    const newHighlightedRevisions = highlightedRevisions.filter(
      (rev) => rev.length,
    );

    if (newHighlightedRevisions.length) {
      params.highlightedRevisions = newHighlightedRevisions;
    }

    if (!selectedDataPoint) {
      delete params.selected;
    } else {
      const { signature_id: signatureId, dataPointId } = selectedDataPoint;

      params.selected = [signatureId, dataPointId].join(',');
    }

    if (Object.keys(zoom).length === 0) {
      delete params.zoom;
    } else {
      params.zoom = [...zoom.x.map((z) => z.getTime()), ...zoom.y].toString();
    }

    this.updateParams(params);
  };

  render() {
    const {
      timeRange,
      testData,
      highlightAlerts,
      highlightedRevisions,
      selectedDataPoint,
      loading,
      errorMessages,
      zoom,
      options,
      colors,
      symbols,
      showModal,
      showTable,
      visibilityChanged,
    } = this.state;

    const { projects, frameworks, user } = this.props;
    return (
      <ErrorBoundary
        errorClasses={errorMessageClass}
        message={genericErrorMessage}
      >
        <Container fluid className="pt-5 pr-5 pl-5">
          {loading && <LoadingSpinner />}

          {errorMessages.length > 0 && (
            <Container className="pb-4 px-0 max-width-default">
              <ErrorMessages errorMessages={errorMessages} />
            </Container>
          )}

          <Row className="justify-content-center">
            {!showTable && (
              <Col
                className={`${testData.length ? 'graph-chooser' : 'col-12'}`}
              >
                <Button
                  className="sr-only"
                  onClick={() => this.setState({ showTable: !showTable })}
                >
                  Table View
                </Button>
                <Container
                  role="region"
                  aria-label="Graph Legend"
                  className="graph-legend pl-0 pb-4"
                >
                  {testData.length > 0 &&
                    testData.map((series) => (
                      <div
                        key={`${series.name} ${series.repository_name} ${series.platform}`}
                      >
                        <LegendCard
                          series={series}
                          testData={testData}
                          {...this.props}
                          updateState={(state) => this.setState(state)}
                          updateStateParams={(state) =>
                            this.setState(state, this.changeParams)
                          }
                          colors={colors}
                          symbols={symbols}
                          selectedDataPoint={selectedDataPoint}
                        />
                      </div>
                    ))}
                </Container>
              </Col>
            )}
            <Col
              className={`pl-0 ${
                testData.length ? 'custom-col-xxl-auto' : 'col-auto'
              } ${showTable && 'w-100'}`}
            >
              {/* Only render the view controls when we're not loading. Otherwise
               the WithSize component provides the wrong sizing information. */}
              {!loading && (
                <GraphsViewControls
                  key={loading ? 'loading' : 'done'}
                  colors={colors}
                  symbols={symbols}
                  timeRange={timeRange}
                  frameworks={frameworks}
                  user={user}
                  projects={projects}
                  options={options}
                  getTestData={this.getTestData}
                  testData={testData}
                  showModal={showModal}
                  showTable={showTable}
                  highlightAlerts={highlightAlerts}
                  highlightedRevisions={highlightedRevisions}
                  zoom={zoom}
                  selectedDataPoint={selectedDataPoint}
                  updateStateParams={(state) =>
                    this.setState(state, this.changeParams)
                  }
                  visibilityChanged={visibilityChanged}
                  updateData={this.updateData}
                  toggle={() => this.setState({ showModal: !showModal })}
                  toggleTableView={() =>
                    this.setState({ showTable: !showTable })
                  }
                  updateTimeRange={(timeRange) =>
                    this.setState(
                      {
                        timeRange,
                        zoom: {},
                        selectedDataPoint: null,
                        colors: [...graphColors],
                        symbols: [...graphSymbols],
                      },
                      this.getTestData,
                    )
                  }
                  hasNoData={!testData.length && !loading}
                />
              )}
            </Col>
          </Row>
        </Container>
      </ErrorBoundary>
    );
  }
}

GraphsView.propTypes = {
  location: PropTypes.shape({
    zoom: PropTypes.string,
    selected: PropTypes.string,
    highlightAlerts: PropTypes.string,
    highlightedRevisions: PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.arrayOf(PropTypes.string),
    ]),
    series: PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.arrayOf(PropTypes.string),
    ]),
  }),
};

GraphsView.defaultProps = {
  location: undefined,
};

export default GraphsView;
