import React from 'react';
import PropTypes from 'prop-types';
import isEqual from 'lodash/isEqual';

import Logo from '../../img/treeherder-logo.png';
import Login from '../../shared/auth/Login';
import LogoMenu from '../../shared/LogoMenu';

import NotificationsMenu from './NotificationsMenu';
import InfraMenu from './InfraMenu';
import ReposMenu from './ReposMenu';
import TiersMenu from './TiersMenu';
import FiltersMenu from './FiltersMenu';
import HelpMenu from './HelpMenu';
import SecondaryNavBar from './SecondaryNavBar';
import HealthMenu from './HealthMenu';

export default class PrimaryNavBar extends React.Component {
  shouldComponentUpdate(prevProps) {
    const {
      filterModel,
      repos,
      user,
      serverChanged,
      groupCountsExpanded,
      duplicateJobsVisible,
      pushHealthVisibility,
    } = this.props;

    return (
      prevProps.filterModel !== filterModel ||
      !isEqual(prevProps.user, user) ||
      !isEqual(prevProps.repos, repos) ||
      prevProps.serverChanged !== serverChanged ||
      prevProps.groupCountsExpanded !== groupCountsExpanded ||
      prevProps.duplicateJobsVisible !== duplicateJobsVisible ||
      prevProps.pushHealthVisibility !== pushHealthVisibility
    );
  }

  render() {
    const {
      user,
      setUser,
      repos,
      updateButtonClick,
      serverChanged,
      filterModel,
      setCurrentRepoTreeStatus,
      duplicateJobsVisible,
      groupCountsExpanded,
      toggleFieldFilterVisible,
      pushHealthVisibility,
      setPushHealthVisibility,
    } = this.props;

    return (
      <div id="global-navbar-container">
        <div id="th-global-top-nav-panel">
          <nav id="th-global-navbar" className="navbar navbar-dark">
            <div id="th-global-navbar-top">
              <LogoMenu menuText="Treeherder" menuImage={Logo} />
              <span className="navbar-right">
                <NotificationsMenu />
                <InfraMenu />
                <ReposMenu repos={repos} />
                <TiersMenu filterModel={filterModel} />
                <FiltersMenu filterModel={filterModel} user={user} />
                <HealthMenu
                  pushHealthVisibility={pushHealthVisibility}
                  setPushHealthVisibility={setPushHealthVisibility}
                />
                <HelpMenu />
                <Login user={user} setUser={setUser} />
              </span>
            </div>
            <SecondaryNavBar
              updateButtonClick={updateButtonClick}
              serverChanged={serverChanged}
              filterModel={filterModel}
              repos={repos}
              setCurrentRepoTreeStatus={setCurrentRepoTreeStatus}
              duplicateJobsVisible={duplicateJobsVisible}
              groupCountsExpanded={groupCountsExpanded}
              toggleFieldFilterVisible={toggleFieldFilterVisible}
            />
          </nav>
        </div>
      </div>
    );
  }
}

PrimaryNavBar.propTypes = {
  updateButtonClick: PropTypes.func.isRequired,
  setUser: PropTypes.func.isRequired,
  setCurrentRepoTreeStatus: PropTypes.func.isRequired,
  toggleFieldFilterVisible: PropTypes.func.isRequired,
  filterModel: PropTypes.object.isRequired,
  repos: PropTypes.array.isRequired,
  serverChanged: PropTypes.bool.isRequired,
  user: PropTypes.object.isRequired,
  duplicateJobsVisible: PropTypes.bool.isRequired,
  groupCountsExpanded: PropTypes.bool.isRequired,
  pushHealthVisibility: PropTypes.string.isRequired,
  setPushHealthVisibility: PropTypes.func.isRequired,
};
