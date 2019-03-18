import React from 'react';
import PropTypes from 'prop-types';
import { react2angular } from 'react2angular/index.es2015';

import perf from '../../js/perf';
import { createQueryParams } from '../../helpers/url';
import { phTimeRanges } from '../../helpers/constants';

import withValidation from './Validation';
import CompareTableView from './CompareTableView';

// TODO remove $stateParams and $state after switching to react router
export class CompareView extends React.PureComponent {
  getInterval = (oldTimestamp, newTimestamp) => {
    const now = new Date().getTime() / 1000;
    let timeRange = Math.min(oldTimestamp, newTimestamp);
    timeRange = Math.round(now - timeRange);
    const newTimeRange = phTimeRanges.find(time => timeRange <= time.value);
    return newTimeRange.value;
  };

  queryParams = (repository, interval, framework) => ({
    repository,
    framework,
    interval,
    no_subtests: true,
  });

  getQueryParams = (timeRange, framework) => {
    const {
      originalProject,
      newProject,
      originalRevision,
      newRevision,
      newResultSet,
      originalResultSet,
    } = this.props.validated;

    let originalParams;
    let interval;

    if (originalRevision) {
      interval = this.getInterval(
        originalResultSet.push_timestamp,
        newResultSet.push_timestamp,
      );
      originalParams = this.queryParams(
        originalProject,
        interval,
        framework.id,
      );
      originalParams.revision = originalRevision;
    } else {
      interval = timeRange.value;
      const startDateMs = (newResultSet.push_timestamp - interval) * 1000;
      const endDateMs = newResultSet.push_timestamp * 1000;

      originalParams = this.queryParams(
        originalProject,
        interval,
        framework.id,
      );
      originalParams.startday = new Date(startDateMs)
        .toISOString()
        .slice(0, -5);
      originalParams.endday = new Date(endDateMs).toISOString().slice(0, -5);
    }

    const newParams = this.queryParams(newProject, interval, framework.id);
    newParams.revision = newRevision;
    return [originalParams, newParams];
  };

  getCustomLink = (links, oldResults, newResults, timeRange, framework) => {
    const {
      originalProject,
      newProject,
      originalRevision,
      newRevision,
    } = this.props.validated;

    const hasSubtests =
      (oldResults && oldResults.has_subtests) ||
      (newResults && newResults.has_subtests);

    if (hasSubtests) {
      const params = {
        originalProject,
        newProject,
        newRevision,
        originalSignature: oldResults ? oldResults.signature_id : null,
        newSignature: newResults ? newResults.signature_id : null,
        framework: framework.id,
      };

      if (originalRevision) {
        params.originalRevision = originalRevision;
      } else {
        params.selectedTimeRange = timeRange.value;
      }
      const detailsLink = `perf.html#/comparesubtest${createQueryParams(
        params,
      )}`;

      links.push({
        title: 'subtests',
        href: detailsLink,
      });
    }
    return links;
  };

  render() {
    return (
      <CompareTableView
        {...this.props}
        getQueryParams={this.getQueryParams}
        getCustomLink={this.getCustomLink}
        checkForResults
        filterByFramework
      />
    );
  }
}

CompareView.propTypes = {
  validated: PropTypes.shape({
    originalResultSet: PropTypes.shape({}),
    newResultSet: PropTypes.shape({}),
    newRevision: PropTypes.string,
    originalProject: PropTypes.string,
    newProject: PropTypes.string,
    originalRevision: PropTypes.string,
    projects: PropTypes.arrayOf(PropTypes.shape({})),
    frameworks: PropTypes.arrayOf(PropTypes.shape({})),
    framework: PropTypes.string,
    updateParams: PropTypes.func.isRequired,
  }),
  $stateParams: PropTypes.shape({}),
  $state: PropTypes.shape({}),
};

CompareView.defaultProps = {
  validated: PropTypes.shape({}),
  $stateParams: null,
  $state: null,
};

const requiredParams = new Set([
  'originalProject',
  'newProject',
  'newRevision',
]);

const compareView = withValidation(requiredParams)(CompareView);

perf.component(
  'compareView',
  react2angular(compareView, [], ['$stateParams', '$state']),
);

export default compareView;
