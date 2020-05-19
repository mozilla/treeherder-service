import React from 'react';
import PropTypes from 'prop-types';

import ProgressBar from '../shared/ProgressBar';

export default class InfraCompareTableRow extends React.PureComponent {
  getColorClass = (data, type) => {
    const { className, isRegression, isImprovement } = data;
    if (type === 'bar' && !isRegression && !isImprovement) return 'secondary';
    if (type === 'background' && className === 'warning')
      return `bg-${className}`;
    if (type === 'text' && className) return `text-${className}`;
    return className;
  };

  render() {
    const { rowLevelResults } = this.props;
    return (
      <React.Fragment>
        <tr>
          <th className="text-left">{rowLevelResults.suite}</th>
          <td>{rowLevelResults.originalValue}</td>
          <td>
            {rowLevelResults.originalValue < rowLevelResults.newValue && (
              <span>&lt;</span>
            )}
            {rowLevelResults.originalValue > rowLevelResults.newValue && (
              <span>&gt;</span>
            )}
          </td>
          <td>{rowLevelResults.newValue}</td>
          <td>{rowLevelResults.originalFailures}</td>
          <td>
            {rowLevelResults.originalFailures < rowLevelResults.newFailures && (
              <span>&lt;</span>
            )}
            {rowLevelResults.originalFailures > rowLevelResults.newFailures && (
              <span>&gt;</span>
            )}
          </td>
          <td>{rowLevelResults.newFailures}</td>
        </tr>
      </React.Fragment>
    );
  }
}

InfraCompareTableRow.propTypes = {
  testName: PropTypes.string.isRequired,
};
