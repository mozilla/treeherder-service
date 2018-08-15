import React from 'react';
import { connect } from 'react-redux';
import { Container, Row, Col } from 'reactstrap';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import Icon from 'react-fontawesome';

import Navigation from './Navigation';
import { fetchBugData, updateDateRange, updateTreeName, updateSelectedBugDetails,
  fetchBugsThenBugDetails } from './redux/actions';
import GenericTable from './GenericTable';
import GraphsContainer from './GraphsContainer';
import { updateQueryParams, calculateMetrics, prettyDate, checkQueryParams,
  processErrorMessage } from './helpers';
import { bugDetailsEndpoint, graphsEndpoint, parseQueryParams, createQueryParams, createApiUrl,
  getJobsUrl } from '../helpers/url';
import BugLogColumn from './BugLogColumn';
import ErrorMessages from './ErrorMessages';
import { stateName } from './constants';

class BugDetailsView extends React.Component {
  constructor(props) {
    super(props);

    this.updateData = this.updateData.bind(this);
    this.setQueryParams = this.setQueryParams.bind(this);
  }

  componentDidMount() {
    this.setQueryParams();
  }

  componentWillReceiveProps(nextProps) {
    const { history, from, to, tree, location, bugId } = nextProps;

    if (location.search !== this.props.location.search) {
      this.updateData(parseQueryParams(location.search));
    }

    // update query params in the address bar if dates or tree are updated via the UI
    if (from !== this.props.from || to !== this.props.to || tree !== this.props.tree) {
      const queryString = createQueryParams({ startday: from, endday: to, tree, bug: bugId });

      updateQueryParams('/bugdetails', queryString, history, this.props.location);
    }

  }

  setQueryParams() {
    const { from, to, tree, location, bugId, fetchData, history } = this.props;

    // data for bug details is provided by MainView, so if the default props are undefined
    // or query strings are missing (user pastes url into address bar), set default values,
    // update url with new query params and update all data
    if (!from || !to || !tree || !bugId) {
      const params = checkQueryParams(parseQueryParams(location.search));
      const queryString = createQueryParams(params);

      updateQueryParams('/bugdetails', queryString, history, location);
      this.updateData(params);
    } else {
      fetchData(createApiUrl(graphsEndpoint, { startday: from, endday: to, tree, bug: bugId }), stateName.detailsViewGraphs);
    }
  }

  updateData(params) {
    const { startday, endday, tree, bug } = params;
    const { updateTree, updateDates, fetchData, bugId, fetchFullBugDetails, updateBugDetails, summary } = this.props;

    updateDates(startday, endday, stateName.detailsView);
    updateTree(tree, stateName.detailsView);
    fetchData(createApiUrl(graphsEndpoint, params), stateName.detailsViewGraphs);

    if (bug !== bugId) {
      updateBugDetails(bug, summary, stateName.detailsView);
      fetchFullBugDetails(createApiUrl(bugDetailsEndpoint, params), stateName.detailsView, bug);
    } else {
      fetchData(createApiUrl(bugDetailsEndpoint, params), stateName.detailsView);
    }
  }

  render() {
    const { graphs, tableFailureMessage, graphFailureMessage, from, to, bugDetails, tree, bugId, summary,
    graphFailureStatus, tableFailureStatus } = this.props;
    const columns = [
      {
        Header: 'Push Time',
        accessor: 'push_time',
      },
      {
        Header: 'Tree',
        accessor: 'tree',
      },
      {
        Header: 'Revision',
        accessor: 'revision',
        Cell: props => <a href={getJobsUrl({ repo: props.original.tree, revision: props.value, selectedJob: props.original.job_id })} target="_blank" rel="noopener noreferrer">{props.value}</a>,
      },
      {
        Header: 'Platform',
        accessor: 'platform',
      },
      {
        Header: 'Build Type',
        accessor: 'build_type',
      },
      {
        Header: 'Test Suite',
        accessor: 'test_suite',
        minWidth: 200,
      },
      {
        Header: 'Machine Name',
        accessor: 'machine_name',
        minWidth: 125,
      },
      {
        Header: 'Log',
        accessor: 'job_id',
        Cell: props => <BugLogColumn {...props} />,
        minWidth: 110,
      },
    ];
    const params = { startday: from, endday: to, tree, bug: bugId };

    let graphOneData = null;
    let graphTwoData = null;

    if (graphs && graphs.length > 0) {
      ({ graphOneData, graphTwoData } = calculateMetrics(graphs));
    }

    return (
      <Container fluid style={{ marginBottom: '5rem', marginTop: '4.5rem', maxWidth: '1200px' }}>
        <Navigation
          params={params}
          tableApi={bugDetailsEndpoint}
          graphApi={graphsEndpoint}
          bugId={bugId}
          name={stateName.detailsView}
          graphName="BUG_DETAILS_GRAPHS"
          tree={tree}
        />
        {tableFailureStatus || graphFailureStatus ?
          <ErrorMessages
            failureMessage={!tableFailureMessage ? graphFailureMessage : tableFailureMessage}
            failureStatus={tableFailureStatus || graphFailureStatus}
          /> :
          <React.Fragment>
            <Row>
              <Col xs="12"><span className="pull-left"><Link to="/"><Icon name="arrow-left" className="pr-1" />
                back</Link></span>
              </Col>
            </Row>
            <Row>
              <Col xs="12" className="mx-auto"><h1>{`Details for Bug ${!bugId ? '' : bugId}`}</h1></Col>
            </Row>
            <Row>
              <Col xs="12" className="mx-auto"><p className="subheader">{`${prettyDate(from)} to ${prettyDate(to)} UTC`}</p>
              </Col>
            </Row>
            {summary &&
            <Row>
              <Col xs="4" className="mx-auto"><p className="text-secondary text-center">{summary}</p></Col>
            </Row>}
            {bugDetails &&
            <Row>
              <Col xs="12" className="mx-auto"><p className="text-secondary">{bugDetails.count} total failures</p></Col>
            </Row>}

            {!graphFailureStatus && graphOneData && graphTwoData ?
              <GraphsContainer
                graphOneData={graphOneData}
                graphTwoData={graphTwoData}
                name={stateName.detailsView}
                tree={tree}
                graphName="BUG_DETAILS_GRAPHS"
                tableApi={bugDetailsEndpoint}
                params={params}
                graphApi={graphsEndpoint}
                bugId={bugId}
                dateOptions
              /> : <p>{processErrorMessage(graphFailureMessage, graphFailureStatus)}</p>}

            {!tableFailureStatus && bugId ?
              <GenericTable
                bugs={bugDetails.results}
                columns={columns}
                name={stateName.detailsView}
                tableApi={bugDetailsEndpoint}
                totalPages={bugDetails.total_pages}
                params={params}
                bugId={bugId}
              /> : <p>{processErrorMessage(tableFailureMessage, tableFailureStatus)}</p>}
          </React.Fragment>}
      </Container>);
  }
}

Container.propTypes = {
  fluid: PropTypes.bool,
};

BugDetailsView.propTypes = {
  bugDetails: PropTypes.oneOfType([
    PropTypes.shape({}),
    PropTypes.shape({
      count: PropTypes.number,
      total_pages: PropTypes.number,
      results: PropTypes.arrayOf(
        PropTypes.shape({
          push_time: PropTypes.string.isRequired,
          platform: PropTypes.string.isRequired,
          revision: PropTypes.string.isRequired,
          test_suite: PropTypes.string.isRequired,
          tree: PropTypes.string.isRequired,
          build_type: PropTypes.string.isRequired,
          job_id: PropTypes.number.isRequired,
          bug_id: PropTypes.number.isRequired,
        }),
      ),
    }),
  ]),
  graphs: PropTypes.oneOfType([
    PropTypes.shape({}),
    PropTypes.arrayOf(
      PropTypes.shape({
        failure_count: PropTypes.number,
        test_runs: PropTypes.number,
        date: PropTypes.string,
      }),
    ),
  ]).isRequired,
  bugzillaData: PropTypes.shape({
    bugs: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.number,
        summary: PropTypes.string,
      }),
    ),
  }).isRequired,
  history: PropTypes.shape({}).isRequired,
  location: PropTypes.shape({
    search: PropTypes.string,
  }).isRequired,
  fetchData: PropTypes.func,
  updateDates: PropTypes.func,
  updateTree: PropTypes.func,
  updateBugDetails: PropTypes.func,
  from: PropTypes.string.isRequired,
  to: PropTypes.string.isRequired,
  tree: PropTypes.string.isRequired,
  bugId: PropTypes.oneOfType([
    PropTypes.string,
    PropTypes.number,
  ]),
  summary: PropTypes.string,
  tableFailureMessage: PropTypes.object,
  graphFailureMessage: PropTypes.object,
  tableFailureStatus: PropTypes.number,
  graphFailureStatus: PropTypes.number,
  fetchFullBugDetails: PropTypes.func,
};

BugDetailsView.defaultProps = {
  tableFailureMessage: null,
  graphFailureMessage: null,
  tableFailureStatus: null,
  graphFailureStatus: null,
  fetchData: null,
  updateTree: null,
  updateDates: null,
  updateBugDetails: null,
  bugDetails: null,
  bugId: null,
  summary: null,
  fetchFullBugDetails: null,
};

const mapStateToProps = state => ({
  bugDetails: state.bugDetailsData.data,
  graphs: state.bugDetailsGraphData.data,
  tableFailureMessage: state.bugDetailsData.message,
  graphFailureMessage: state.bugDetailsGraphData.message,
  tableFailureStatus: state.bugDetailsData.failureStatus,
  graphFailureStatus: state.bugDetailsGraphData.failureStatus,
  from: state.bugDetailsDates.from,
  to: state.bugDetailsDates.to,
  tree: state.bugDetailsTree.tree,
  bugId: state.bugDetails.bugId,
  summary: state.bugDetails.summary,
  bugzillaData: state.bugzillaBugDetails.data,
});

const mapDispatchToProps = dispatch => ({
  fetchData: (url, name) => dispatch(fetchBugData(url, name)),
  updateDates: (from, to, name) => dispatch(updateDateRange(from, to, name)),
  updateTree: (tree, name) => dispatch(updateTreeName(tree, name)),
  updateBugDetails: (bugId, summary, name) => dispatch(updateSelectedBugDetails(bugId, summary, name)),
  fetchFullBugDetails: (url, name, bug) => dispatch(fetchBugsThenBugDetails(url, name, bug)),
});

export default connect(mapStateToProps, mapDispatchToProps)(BugDetailsView);
