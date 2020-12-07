import React from 'react';
import PropTypes from 'prop-types';
import countBy from 'lodash/countBy';
import moment from 'moment';
import { Button } from 'reactstrap';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faExclamationCircle,
  faTimes,
} from '@fortawesome/free-solid-svg-icons';
import { Link } from 'react-router-dom';

import { alertStatusMap, endpoints } from '../constants';
import { getJobsUrl, createQueryParams, getApiUrl } from '../../helpers/url';
import { create } from '../../helpers/http';
import RepositoryModel from '../../models/repository';
import { displayNumber, getStatus } from '../helpers';
import Clipboard from '../../shared/Clipboard';

const TOOLTIP_WIDTH = 280;

const GraphTooltip = ({
  testData,
  user,
  updateData,
  projects,
  updateStateParams,
  lockTooltip,
  closeTooltip,
  datum,
  x,
  y,
  graphWidth,
}) => {
  const testDetails = testData.find(
    (item) => item.signature_id === datum.signature_id,
  );

  const flotIndex = testDetails.data.findIndex((item) =>
    datum.dataPointId
      ? item.dataPointId === datum.dataPointId
      : item.pushId === datum.pushId,
  );
  const dataPointDetails = testDetails.data[flotIndex];

  const retriggers = countBy(testDetails.resultSetData, (resultSetId) =>
    resultSetId === datum.pushId ? 'retrigger' : 'original',
  );
  const retriggerNum = retriggers.retrigger - 1;
  const prevFlotDataPointIndex = flotIndex - 1;
  const value = dataPointDetails.y;

  const v0 =
    prevFlotDataPointIndex !== -1
      ? testDetails.data[prevFlotDataPointIndex].y
      : value;
  const deltaValue = value - v0;
  const deltaPercent = value / v0 - 1;
  let alert;
  let alertStatus;

  if (dataPointDetails.alertSummary && dataPointDetails.alertSummary.alerts) {
    alert = dataPointDetails.alertSummary.alerts.find(
      (alert) => alert.series_signature.id === testDetails.signature_id,
    );
  }

  if (alert) {
    alertStatus =
      alert.status === alertStatusMap.acknowledged && testDetails.alertSummary
        ? getStatus(testDetails.alertSummary.status)
        : getStatus(alert.status, alertStatusMap);
  }

  const repositoryName = projects.find(
    (repositoryName) => repositoryName.name === testDetails.repository_name,
  );

  let prevRevision;
  let prevPushId;
  let pushUrl;
  const firstTriggerIndex = testDetails.data.findIndex(
    (e) => e.revision === dataPointDetails.revision,
  );
  if (prevFlotDataPointIndex !== -1 && firstTriggerIndex > 0) {
    prevRevision = testDetails.data[firstTriggerIndex - 1].revision;
    prevPushId = testDetails.data[prevFlotDataPointIndex].pushId;
    const repoModel = new RepositoryModel(repositoryName);
    pushUrl = repoModel.getPushLogRangeHref({
      fromchange: prevRevision,
      tochange: dataPointDetails.revision,
    });
  }

  const jobsUrl = getJobsUrl({
    repo: testDetails.repository_name,
    revision: dataPointDetails.revision,
    selectedJob: dataPointDetails.jobId,
    group_state: 'expanded',
  });

  const createAlert = async () => {
    let data;
    let failureStatus;

    ({ data, failureStatus } = await create(getApiUrl(endpoints.alertSummary), {
      repository_id: testDetails.projectId,
      framework_id: testDetails.framework_id,
      push_id: dataPointDetails.pushId,
      prev_push_id: prevPushId,
    }));

    if (failureStatus) {
      return updateStateParams({
        errorMessages: [
          `Failed to create an alert summary for push ${dataPointDetails.push_id}: ${data}`,
        ],
      });
    }

    const newAlertSummaryId = data.alert_summary_id;
    ({ data, failureStatus } = await create(getApiUrl(endpoints.alert), {
      summary_id: newAlertSummaryId,
      signature_id: testDetails.signature_id,
    }));

    if (failureStatus) {
      updateStateParams({
        errorMessages: [
          `Failed to create an alert for alert summary ${newAlertSummaryId}: ${data}`,
        ],
      });
    }

    updateData(
      testDetails.signature_id,
      testDetails.projectId,
      newAlertSummaryId,
      flotIndex,
    );
  };

  // Ensure the tooltip does not leave the graph.
  let tooltipLeft = x - TOOLTIP_WIDTH / 2;
  const tooltipRight = x + TOOLTIP_WIDTH / 2;
  let arrowOffset = 0;
  if (tooltipRight > graphWidth) {
    // The tooltip is off the right of the container.
    arrowOffset = tooltipRight - graphWidth;
    tooltipLeft -= arrowOffset;
  }
  if (tooltipLeft < 0) {
    // The tooltip is off the left of the container.
    arrowOffset = tooltipLeft;
    tooltipLeft = 0;
  }

  // const tooltipTop = y - 201;
  const tooltipTop = y;

  return (
    <foreignObject
      width="100%"
      height="100%"
      className="graph-tooltip-foreign-object"
    >
      <div
        className="graph-tooltip-positioner"
        style={{
          left: tooltipLeft,
          top: tooltipTop,
        }}
      >
        <div
          className={`graph-tooltip ${lockTooltip ? 'locked' : null}`}
          xmlns="http://www.w3.org/1999/xhtml"
          data-testid="graphTooltip"
        >
          <Button
            outline
            color="secondary"
            className="close mr-3 my-2 ml-2"
            onClick={closeTooltip}
          >
            <FontAwesomeIcon
              className="pointer text-white"
              icon={faTimes}
              size="xs"
              title="close tooltip"
            />
          </Button>
          <div className="body">
            <div>
              <p data-testid="repoName">({testDetails.repository_name})</p>
              <p className="small" data-testid="platform">
                {testDetails.platform}
              </p>
            </div>
            <div>
              <p>
                {displayNumber(value)}
                {testDetails.measurementUnit && (
                  <span> {testDetails.measurementUnit}</span>
                )}
                <span className="text-muted">
                  {testDetails.lowerIsBetter
                    ? ' (lower is better)'
                    : ' (higher is better)'}
                </span>
              </p>
              <p className="small">
                &Delta; {displayNumber(deltaValue.toFixed(1))} (
                {(100 * deltaPercent).toFixed(1)}%)
              </p>
            </div>

            <div>
              <span>
                <a href={pushUrl} target="_blank" rel="noopener noreferrer">
                  {dataPointDetails.revision.slice(0, 13)}
                </a>{' '}
                {(dataPointDetails.jobId || prevRevision) && '('}
                {dataPointDetails.jobId && (
                  <a href={jobsUrl} target="_blank" rel="noopener noreferrer">
                    job
                  </a>
                )}
                {dataPointDetails.jobId && prevRevision && ', '}
                {prevRevision && (
                  <a
                    href={`./comparesubtest${createQueryParams({
                      originalProject: testDetails.repository_name,
                      newProject: testDetails.repository_name,
                      originalRevision: prevRevision,
                      newRevision: dataPointDetails.revision,
                      originalSignature:
                        testDetails.parentSignature || testDetails.signature_id,
                      newSignature:
                        testDetails.parentSignature || testDetails.signature_id,
                      framework: testDetails.framework_id,
                    })}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    compare
                  </a>
                )}
                {(dataPointDetails.jobId || prevRevision) && ') '}
                <Clipboard
                  text={dataPointDetails.revision}
                  description="Revision"
                  outline
                />
              </span>
              {dataPointDetails.alertSummary && (
                <p>
                  <Link to={`./alerts?id=${dataPointDetails.alertSummary.id}`}>
                    <FontAwesomeIcon
                      className="text-warning"
                      icon={faExclamationCircle}
                      size="sm"
                    />
                    {` Alert # ${dataPointDetails.alertSummary.id}`}
                  </Link>
                  <span className="text-muted">
                    {` - ${alertStatus} `}
                    {alert && alert.related_summary_id && (
                      <span>
                        {alert.related_summary_id !==
                        dataPointDetails.alertSummary.id
                          ? 'to'
                          : 'from'}
                        <Link
                          to={`./alerts?id=${alert.related_summary_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >{` alert # ${alert.related_summary_id}`}</Link>
                      </span>
                    )}
                  </span>
                </p>
              )}
              {!dataPointDetails.alertSummary && prevPushId && (
                <p className="pt-2">
                  {user.isStaff ? (
                    <Button
                      color="darker-info"
                      outline
                      size="sm"
                      onClick={createAlert}
                    >
                      create alert
                    </Button>
                  ) : (
                    <span>(log in as a a sheriff to create)</span>
                  )}
                </p>
              )}
              <p className="small text-white pt-2">{`${moment
                .utc(dataPointDetails.x)
                .format('MMM DD hh:mm:ss')} UTC`}</p>
              {Boolean(retriggerNum) && (
                <p className="small">{`Retriggers: ${retriggerNum}`}</p>
              )}
            </div>
          </div>
          <div
            className="tip"
            style={{ left: TOOLTIP_WIDTH / 2 + arrowOffset }}
          />
        </div>
      </div>
    </foreignObject>
  );
};

GraphTooltip.propTypes = {
  dataPoint: PropTypes.shape({}),
  testData: PropTypes.arrayOf(PropTypes.shape({})).isRequired,
  user: PropTypes.shape({}).isRequired,
  updateData: PropTypes.func.isRequired,
  projects: PropTypes.arrayOf(PropTypes.shape({})),
  graphWidth: PropTypes.number.isRequired,
};

GraphTooltip.defaultProps = {
  projects: [],
  dataPoint: undefined,
};

export default GraphTooltip;
